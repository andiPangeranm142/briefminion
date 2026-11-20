"""OpenMinion tools for BriefMinion.

Tools are built by :func:`create_tools` so each run gets its own run-scoped
store: the agent drives the tools, and the orchestrator reads back what the
agent found (search results, fetched articles) from the store afterwards.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from openminion import tool

from .rss import NewsItem, fetch_url_text, search_news_items


@dataclass
class FetchedArticle:
    url: str
    title: str
    text: str


@dataclass
class RunStore:
    """What the agent found during one brief run."""

    search_results: list[NewsItem] = field(default_factory=list)
    articles: list[FetchedArticle] = field(default_factory=list)
    saved_path: str | None = None


def create_tools(store: RunStore, out_dir: str):
    """Build the three BriefMinion tools bound to one run store."""

    @tool(min_scope="READ_ONLY", idempotent=True)
    def search_news(topic: str, max_results: int = 8) -> str:
        """Search live news for a topic. Returns numbered headlines with links."""
        try:
            items = search_news_items(topic, max_results=max_results)
        except Exception as exc:  # noqa: BLE001 - report to the agent, don't crash the turn
            return f"ERROR: news search failed: {exc}"
        if not items:
            return "No news items found for this topic."
        store.search_results = items
        lines = []
        for index, item in enumerate(items, start=1):
            stamp = f", {item.published}" if item.published else ""
            source = f" ({item.source})" if item.source else ""
            lines.append(f"{index}. {item.title}{source}{stamp}\n   {item.link}")
        return "\n".join(lines)

    @tool(min_scope="READ_ONLY", idempotent=True)
    def fetch_article(url: str) -> str:
        """Fetch one article URL and return its visible text (truncated)."""
        try:
            text = fetch_url_text(url, max_chars=2000)
        except Exception as exc:  # noqa: BLE001 - report to the agent, don't crash the turn
            return f"ERROR: could not fetch {url}: {exc}"
        if not text:
            return f"ERROR: no readable text at {url}."
        title = next(
            (item.title for item in store.search_results if item.link == url),
            url,
        )
        if all(article.url != url for article in store.articles):
            store.articles.append(FetchedArticle(url=url, title=title, text=text))
        return f"Article: {title}\n{text}"

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
