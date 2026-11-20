"""OpenMinion tools for BriefMinion.

Tools are built by :func:`create_tools` so each run gets its own run-scoped
store: the agent drives the tools, and the orchestrator reads back what the
agent found (search results, fetched articles) from the store afterwards.

``search_news`` and ``fetch_article`` return structured dicts (not plain
text) for two reasons:

* the model reads JSON just as well, and structured results keep titles,
  URLs and dates unambiguous; and
* the SDK's freshness verifier only accepts tool-output evidence that
  carries a dated key (``retrieved_at`` / ``published_at``) in the
  agent's own turn — a plain-text result has no such keys, so a turn
  that only saw text fails verification (see docs/BUILDING_BLOCKS.md
  finding 17). Every successful result therefore includes
  ``retrieved_at`` (and ``published_at`` when the feed provides it).

The tools also enforce per-run budgets, because a free-tier model in the
SDK's tool loop does not reliably stop on its own: in our first live
probe the research agent searched 8+ times with new queries and fetched
30 articles instead of stopping at 2 (see BUILDING_BLOCKS.md finding
19). The budgets are deterministic — the model cannot loop past them —
and every budget refusal tells the model exactly what to do next
(stop calling tools and answer with what it has):

* ``search_news``: exactly one search per run.
* ``fetch_article``: new URLs only while fewer than ``max_sources``
  articles have been fetched successfully, and at most
  ``max_sources + 4`` distinct fetch attempts (slack for 403s).
  Re-fetching an already-fetched URL is always allowed and returns the
  cached text — the digest subagent and the composer re-read the same
  sources the research phase found.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from openminion import tool

from .rss import NewsItem, fetch_url_text, search_news_items


@dataclass
class FetchedArticle:
    url: str
    title: str
    text: str
    published: str = ""


@dataclass
class RunStore:
    """What the agent found during one brief run."""

    search_results: list[NewsItem] = field(default_factory=list)
    articles: list[FetchedArticle] = field(default_factory=list)
    saved_path: str | None = None
    search_calls: int = 0
    fetch_attempts: set[str] = field(default_factory=set)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_tools(store: RunStore, out_dir: str, max_sources: int = 4):
    """Build the three BriefMinion tools bound to one run store.

    ``max_sources`` caps the articles the research phase may fetch; the
    fetch-attempt budget is ``max_sources + 4`` distinct URLs (slack for
    publishers that refuse to serve, e.g. HTTP 403).
    """
    fetch_attempt_budget = max_sources + 4

    @tool(min_scope="READ_ONLY", idempotent=True)
    def search_news(topic: str, max_results: int = 8) -> dict[str, Any]:
        """Search live news for a topic.

        Returns a JSON object: {"query", "retrieved_at", "results"},
        where each result has "title", "url", "published" and "source".
        Only one search per run: a second call returns an error telling
        the agent to use the first search's results.
        """
        if store.search_calls >= 1:
            if store.search_results:
                return {
                    "error": (
                        "Search already done once for this run. Do not search "
                        "again. Use the results from the first search: fetch "
                        "articles from those results, then reply with one line "
                        "per fetched article."
                    )
                }
            return {
                "error": (
                    "The news search already ran and returned nothing "
                    "usable. Do not search again; reply that no news could "
                    "be found for this topic."
                )
            }
        store.search_calls += 1
        try:
            items = search_news_items(topic, max_results=max_results)
        except Exception as exc:  # noqa: BLE001 - report to the agent, don't crash the turn
            return {"error": f"news search failed: {exc}"}
        store.search_results = items
        return {
            "query": topic,
            "retrieved_at": _now_iso(),
            "results": [
                {
                    "title": item.title,
                    "url": item.link,
                    "published": item.published,
                    "source": item.source,
                }
                for item in items
            ],
        }

    @tool(min_scope="READ_ONLY", idempotent=True)
    def fetch_article(url: str) -> dict[str, Any]:
        """Fetch one article URL and return its visible text (truncated).

        Returns a JSON object: {"title", "url", "published_at",
        "retrieved_at", "text"}. Re-fetching an already-fetched URL
        returns the cached text. New URLs are refused once max_sources
        articles are fetched or the fetch-attempt budget is used up.
        """
        cached = next(
            (article for article in store.articles if article.url == url),
            None,
        )
        if cached is not None:
            return {
                "title": cached.title,
                "url": cached.url,
                "published_at": cached.published,
                "retrieved_at": _now_iso(),
                "text": cached.text,
            }
        if url in store.fetch_attempts:
            # Attempted before and failed (a success would be cached
            # above): do not retry the same dead URL.
            return {
                "error": (
                    f"Already tried {url} and it failed. Do not retry it; "
                    "try a different URL from the search results, or "
                    "proceed with the articles you already have."
                )
            }
        if len(store.articles) >= max_sources:
            return {
                "error": (
                    f"You already have {max_sources} fetched articles. "
                    "Do not call fetch_article again; proceed with the "
                    "articles you already have."
                )
            }
        if len(store.fetch_attempts) >= fetch_attempt_budget:
            return {
                "error": (
                    "Fetch budget used. Do not call fetch_article again; "
                    "proceed with the articles you already have."
                )
            }
        store.fetch_attempts.add(url)
        try:
            text = fetch_url_text(url, max_chars=2000)
        except Exception as exc:  # noqa: BLE001 - report to the agent, don't crash the turn
            return {"error": f"could not fetch {url}: {exc}"}
        if not text:
            return {"error": f"no readable text at {url}"}
        matched = next(
            (item for item in store.search_results if item.link == url),
            None,
        )
        title = matched.title if matched else url
        published = matched.published if matched else ""
        store.articles.append(
            FetchedArticle(url=url, title=title, text=text, published=published)
        )
        return {
            "title": title,
            "url": url,
            "published_at": published,
            "retrieved_at": _now_iso(),
            "text": text,
        }

    @tool(dangerous=True)
    def save_brief(filename: str, content: str) -> str:
        """Save the finished brief as a Markdown file. Needs human approval."""
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".md"):
            return "ERROR: filename must end with .md"
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, safe_name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        store.saved_path = path
        return f"Saved brief to {path}"

    return search_news, fetch_article, save_brief
