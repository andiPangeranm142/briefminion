"""Tests for the OpenMinion tools (called directly, no model needed)."""

from briefminion.rss import NewsItem
from briefminion.tools import RunStore, create_tools


def test_save_brief_writes_file_and_records_path(tmp_path):
    store = RunStore()
    _, _, save_brief = create_tools(store, str(tmp_path))
    result = save_brief("my-brief-2026-11-20.md", "# Hello\n")
    assert "Saved brief to" in result
    assert (tmp_path / "my-brief-2026-11-20.md").read_text() == "# Hello\n"
    assert store.saved_path == str(tmp_path / "my-brief-2026-11-20.md")


def test_save_brief_rejects_non_markdown(tmp_path):
    store = RunStore()
    _, _, save_brief = create_tools(store, str(tmp_path))
    assert save_brief("evil.txt", "x").startswith("ERROR")
    assert store.saved_path is None


def test_save_brief_strips_directories(tmp_path):
    store = RunStore()
    _, _, save_brief = create_tools(store, str(tmp_path))
    result = save_brief("../escape.md", "# x")
    assert "Saved brief to" in result
    assert (tmp_path / "escape.md").exists()
    assert not (tmp_path.parent / "escape.md").exists()


def test_search_news_records_results_in_store(monkeypatch):
    store = RunStore()
    search_news, _, _ = create_tools(store, "/tmp")
    items = [
        NewsItem(
            title="Headline",
            link="https://example.com/h",
            published="Fri, 20 Nov 2026",
            source="Outlet",
        )
    ]
    monkeypatch.setattr(
        "briefminion.tools.search_news_items", lambda topic, max_results=8: items
    )
    result = search_news("quantum", max_results=5)
    assert result["query"] == "quantum"
    assert result["retrieved_at"]  # dated evidence for the SDK freshness guard
    assert result["results"] == [
        {
            "title": "Headline",
            "url": "https://example.com/h",
            "published": "Fri, 20 Nov 2026",
            "source": "Outlet",
        }
    ]
    assert store.search_results == items


def test_search_news_reports_errors_instead_of_raising(monkeypatch):
    store = RunStore()
    search_news, _, _ = create_tools(store, "/tmp")
    monkeypatch.setattr(
        "briefminion.tools.search_news_items",
        lambda topic, max_results=8: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = search_news("quantum")
    assert result["error"].startswith("news search failed")


def test_fetch_article_records_article_once(monkeypatch):
    store = RunStore()
    store.search_results = [
        NewsItem(
            title="T",
            link="https://example.com/a",
            published="Fri, 20 Nov 2026",
            source="",
        )
    ]
    _, fetch_article, _ = create_tools(store, "/tmp")
    monkeypatch.setattr(
        "briefminion.tools.fetch_url_text",
        lambda url, max_chars=2000: "article body",
    )
    result = fetch_article("https://example.com/a")
    assert result["title"] == "T"
    assert result["text"] == "article body"
    assert result["published_at"] == "Fri, 20 Nov 2026"
    assert result["retrieved_at"]  # dated evidence for the SDK freshness guard
    fetch_article("https://example.com/a")  # second call: no duplicate
    assert len(store.articles) == 1
    assert store.articles[0].text == "article body"
    assert store.articles[0].published == "Fri, 20 Nov 2026"
