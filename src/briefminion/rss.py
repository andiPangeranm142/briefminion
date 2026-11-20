"""Live news lookup through the Google News RSS feed (no API key needed).

The feed is a public, keyless HTTP endpoint, which keeps the whole workflow
free: the only credential BriefMinion needs is the model provider key.
"""

from __future__ import annotations

import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

RSS_BASE = "https://news.google.com/rss/search"
USER_AGENT = "BriefMinion/0.1 (+https://github.com/andiPangeranm142/briefminion)"
FETCH_TIMEOUT_SECONDS = 20
# Google News RSS rate-limits repeated calls (HTTP 429); back off and retry.
RETRY_BACKOFF_SECONDS = (10, 25, 60)


def _urlopen_with_retry(request: urllib.request.Request, timeout: int):
    """Open a URL, retrying 429/503 responses with backoff."""
    last_error: urllib.error.HTTPError | None = None
    for wait in list(RETRY_BACKOFF_SECONDS) + [None]:
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 503) and wait is not None:
                time.sleep(wait)
                continue
            raise
    assert last_error is not None  # loop always returns or raises
    raise last_error


@dataclass
class NewsItem:
    title: str
    link: str
    published: str
    source: str


def search_url(topic: str) -> str:
    """Build the Google News RSS search URL for a topic."""
    query = urllib.parse.urlencode(
        {"q": topic, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    return f"{RSS_BASE}?{query}"


def parse_rss(xml_text: str, max_results: int = 8) -> list[NewsItem]:
    """Parse Google News RSS XML into a list of news items.

    Google News puts the outlet name at the end of the title
    ("Headline text - Outlet Name"); split it off when present.
    """
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for element in root.iter("item"):
        if len(items) >= max_results:
            break
        title = (element.findtext("title") or "").strip()
        link = (element.findtext("link") or "").strip()
        published = (element.findtext("pubDate") or "").strip()
        source = ""
        if " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append(
            NewsItem(
                title=html.unescape(title),
                link=link,
                published=published,
                source=html.unescape(source),
            )
        )
    return items


def search_news_items(topic: str, max_results: int = 8) -> list[NewsItem]:
    """Fetch and parse the Google News RSS feed for a topic."""
    request = urllib.request.Request(
        search_url(topic), headers={"User-Agent": USER_AGENT}
    )
    with _urlopen_with_retry(request, FETCH_TIMEOUT_SECONDS) as response:
        xml_text = response.read().decode("utf-8", errors="replace")
    return parse_rss(xml_text, max_results=max_results)


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def html_to_text(html_text: str) -> str:
    """Strip tags, scripts and styles from HTML and collapse whitespace."""
    without_scripts = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = _TAG_RE.sub(" ", without_scripts)
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def fetch_url_text(url: str, max_chars: int = 2000) -> str:
    """Fetch a URL and return its visible text, truncated to max_chars."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_with_retry(request, FETCH_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return html_to_text(raw)[:max_chars]
