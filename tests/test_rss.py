"""Tests for the RSS/news helpers (no model needed)."""

import io
import urllib.error
import urllib.request

import pytest

from briefminion.rss import (
    NewsItem,
    _urlopen_with_retry,
    fetch_url_text,
    html_to_text,
    parse_bing_rss,
    parse_rss,
    search_bing_news_items,
    search_bing_url,
    search_google_news_items,
    search_news_items,
    search_url,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>test</title>
<item>
  <title>Quantum leap in error correction - Nature News</title>
  <link>https://example.com/quantum-leap</link>
  <pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate>
</item>
<item>
  <title>Second headline without outlet</title>
  <link>https://example.com/second</link>
  <pubDate>Thu, 19 Nov 2026 09:00:00 GMT</pubDate>
</item>
</channel></rss>
"""

SAMPLE_BING_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Bing News</title>
<item>
  <title>AI chips race heats up</title>
  <link>https://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3A%2F%2Fexample.com%2Fai-chips</link>
  <pubDate>Fri, 20 Nov 2026 11:00:00 GMT</pubDate>
</item>
<item>
  <title>Plain link without redirect param</title>
  <link>https://example.com/plain</link>
  <pubDate>Thu, 19 Nov 2026 09:00:00 GMT</pubDate>
</item>
</channel></rss>
"""


def test_search_url_encodes_topic():
    url = search_url("quantum computing")
    assert url.startswith("https://news.google.com/rss/search?")
    assert "q=quantum+computing" in url
    assert "hl=en-US" in url


def test_search_bing_url_encodes_topic():
    url = search_bing_url("quantum computing")
    assert url.startswith("https://www.bing.com/news/search?")
    assert "q=quantum+computing" in url
    assert "format=rss" in url


def test_parse_bing_rss_extracts_direct_url_and_caps_results():
    items = parse_bing_rss(SAMPLE_BING_RSS, max_results=1)
    assert len(items) == 1
    assert items[0].title == "AI chips race heats up"
    # The apiclick redirect's url= parameter is the real publisher URL.
    assert items[0].link == "https://example.com/ai-chips"
    assert items[0].published == "Fri, 20 Nov 2026 11:00:00 GMT"


def test_parse_bing_rss_keeps_plain_links():
    items = parse_bing_rss(SAMPLE_BING_RSS, max_results=8)
    assert items[1].link == "https://example.com/plain"


def test_parse_rss_splits_outlet_and_caps_results():
    items = parse_rss(SAMPLE_RSS, max_results=1)
    assert len(items) == 1
    assert items[0].title == "Quantum leap in error correction"
    assert items[0].source == "Nature News"
    assert items[0].link == "https://example.com/quantum-leap"
    assert items[0].published == "Fri, 20 Nov 2026 10:00:00 GMT"


def test_parse_rss_keeps_title_without_outlet():
    items = parse_rss(SAMPLE_RSS, max_results=8)
    assert items[1].title == "Second headline without outlet"
    assert items[1].source == ""


def test_html_to_text_strips_tags_scripts_and_entities():
    html_text = (
        "<html><head><style>.x{color:red}</style>"
        "<script>var a = 1;</script></head>"
        "<body><h1>Head &amp; line</h1><p>First  paragraph.</p></body></html>"
    )
    assert html_to_text(html_text) == "Head & line First paragraph."


def test_urlopen_retries_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(request, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"")
            )
        return io.BytesIO(b"ok")

    monkeypatch.setattr("briefminion.rss.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("briefminion.rss.time.sleep", lambda seconds: None)
    response = _urlopen_with_retry(
        urllib.request.Request("https://example.com"),
        timeout=5,
    )
    assert response.read() == b"ok"
    assert calls["n"] == 3


def test_urlopen_does_not_retry_404(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(request, timeout):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            request.full_url, 404, "Not Found", {}, io.BytesIO(b"")
        )

    monkeypatch.setattr("briefminion.rss.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("briefminion.rss.time.sleep", lambda seconds: None)
    with pytest.raises(urllib.error.HTTPError):
        _urlopen_with_retry(
            urllib.request.Request("https://example.com"),
            timeout=5,
        )
    assert calls["n"] == 1


def test_live_google_news_rss_returns_items():
    """Live check: the keyless Google RSS endpoint works from this machine."""
    items = search_google_news_items("quantum computing", max_results=3)
    assert len(items) >= 1
    assert isinstance(items[0], NewsItem)
    assert items[0].title
    assert items[0].link.startswith("http")


def test_live_bing_news_rss_returns_direct_links():
    """Live check: Bing RSS works and its links resolve to publishers."""
    items = search_bing_news_items("quantum computing", max_results=3)
    assert len(items) >= 1
    assert isinstance(items[0], NewsItem)
    assert items[0].title
    assert items[0].link.startswith("http")
    assert "bing.com" not in items[0].link  # redirect unwrapped


def test_live_search_news_items_prefers_bing():
    """Live check: the combined search returns fetchable (non-Bing) links."""
    items = search_news_items("quantum computing", max_results=3)
    assert len(items) >= 1
    assert all("bing.com" not in item.link for item in items)


def test_live_fetch_url_text_reads_a_real_page():
    text = fetch_url_text("https://example.com", max_chars=500)
    assert "Example Domain" in text
    assert len(text) <= 500
