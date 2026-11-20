"""Live news lookup through keyless RSS feeds (no API key needed).

Two sources, both public and keyless:

* **Bing News RSS (primary)** — ``https://www.bing.com/news/search``.
  Its ``<link>`` values are redirect URLs whose ``url`` query parameter
  carries the real publisher URL, so the articles are fetchable.
* **Google News RSS (fallback)** — ``https://news.google.com/rss/search``.
  Its ``CBM...`` article URLs are encrypted/obfuscated and cannot be
  resolved to the publisher, so Google is only used when Bing fails and
  the returned items are effectively title-only (see
  docs/BUILDING_BLOCKS.md finding 18).

The feeds keep the whole workflow free: the only credential BriefMinion
needs is the model provider key.
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
BING_RSS_BASE = "https://www.bing.com/news/search"
USER_AGENT = "BriefMinion/0.1 (+https://github.com/andiPangeranm142/briefminion)"
# A browser UA: several publishers (and Bing) serve less, or 403, to a bare
# library UA. Article fetches and Bing RSS use this; Google RSS keeps the
# bot UA.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
FETCH_TIMEOUT_SECONDS = 20
# News RSS endpoints rate-limit repeated calls (HTTP 429); back off and retry.
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


def search_bing_url(topic: str) -> str:
    """Build the Bing News RSS search URL for a topic."""
    query = urllib.parse.urlencode(
        {"q": topic, "format": "rss", "cc": "us", "setlang": "en"}
    )
    return f"{BING_RSS_BASE}?{query}"


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


def _bing_direct_url(link: str) -> str:
    """Extract the real publisher URL from a Bing News redirect link.

    Bing links look like ``.../news/apiclick.aspx?ref=FexRss&url=<encoded>``;
    the ``url`` query parameter carries the publisher URL. If there is no
    such parameter, return the link unchanged.
    """
    parsed = urllib.parse.urlparse(link)
    params = urllib.parse.parse_qs(parsed.query)
    direct = params.get("url", [""])[0].strip()
    return direct or link


def parse_bing_rss(xml_text: str, max_results: int = 8) -> list[NewsItem]:
    """Parse Bing News RSS XML into a list of news items.

    Bing titles carry no outlet suffix; the outlet is not reliably
    available, so ``source`` is left empty and callers derive it from the
    link's host when needed.
    """
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for element in root.iter("item"):
        if len(items) >= max_results:
            break
        title = (element.findtext("title") or "").strip()
        link = (element.findtext("link") or "").strip()
        published = (element.findtext("pubDate") or "").strip()
        items.append(
            NewsItem(
                title=html.unescape(title),
                link=_bing_direct_url(link),
                published=published,
                source="",
            )
        )
    return items


def search_google_news_items(topic: str, max_results: int = 8) -> list[NewsItem]:
    """Fetch and parse the Google News RSS feed for a topic."""
    request = urllib.request.Request(
        search_url(topic), headers={"User-Agent": USER_AGENT}
    )
    with _urlopen_with_retry(request, FETCH_TIMEOUT_SECONDS) as response:
        xml_text = response.read().decode("utf-8", errors="replace")
    return parse_rss(xml_text, max_results=max_results)


def search_bing_news_items(topic: str, max_results: int = 8) -> list[NewsItem]:
    """Fetch and parse the Bing News RSS feed for a topic."""
    request = urllib.request.Request(
        search_bing_url(topic), headers={"User-Agent": BROWSER_USER_AGENT}
    )
    with _urlopen_with_retry(request, FETCH_TIMEOUT_SECONDS) as response:
        xml_text = response.read().decode("utf-8", errors="replace")
    return parse_bing_rss(xml_text, max_results=max_results)


def search_news_items(topic: str, max_results: int = 8) -> list[NewsItem]:
    """Fetch news items for a topic: Bing News first, Google News fallback.

    Bing is primary because its links resolve to real publisher URLs;
    Google News CBM links cannot be fetched (see module docstring).
    """
    try:
        items = search_bing_news_items(topic, max_results=max_results)
    except Exception:
        items = []
    if items:
        return items
    return search_google_news_items(topic, max_results=max_results)


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
    request = urllib.request.Request(
        url, headers={"User-Agent": BROWSER_USER_AGENT}
    )
    with _urlopen_with_retry(request, FETCH_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return html_to_text(raw)[:max_chars]
