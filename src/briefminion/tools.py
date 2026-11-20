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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_tools(store: RunStore, out_dir: str):
    """Build the three BriefMinion tools bound to one run store."""

    @tool(min_scope="READ_ONLY", idempotent=True)
    def search_news(topic: str, max_results: int = 8) -> dict[str, Any]:
        """Search live news for a topic.

        Returns a JSON object: {"query", "retrieved_at", "results"},
        where each result has "title", "url", "published" and "source".
        """
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
        "retrieved_at", "text"}.
        """
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
        if all(article.url != url for article in store.articles):
            store.articles.append(
                FetchedArticle(
                    url=url, title=title, text=text, published=published
                )
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
