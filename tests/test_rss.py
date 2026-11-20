"""Tests for the RSS/news helpers (no model needed)."""

from briefminion.rss import (
    NewsItem,
    fetch_url_text,
    html_to_text,
    parse_rss,
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


def test_search_url_encodes_topic():
    url = search_url("quantum computing")
    assert url.startswith("https://news.google.com/rss/search?")
    assert "q=quantum+computing" in url
    assert "hl=en-US" in url


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


def test_live_google_news_rss_returns_items():
    """Live check: the keyless RSS endpoint works from this machine."""
    items = search_news_items("quantum computing", max_results=3)
    assert len(items) >= 1
    assert isinstance(items[0], NewsItem)
    assert items[0].title
    assert items[0].link.startswith("http")


def test_live_fetch_url_text_reads_a_real_page():
    text = fetch_url_text("https://example.com", max_chars=500)
    assert "Example Domain" in text
    assert len(text) <= 500
