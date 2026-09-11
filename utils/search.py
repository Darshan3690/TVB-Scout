"""Public web-search adapter with optional SerpAPI support."""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

from utils.logging import get_logger

LOGGER = get_logger("SEARCH")


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class SearchClient:
    """Uses SerpAPI when configured, otherwise DuckDuckGo's public HTML endpoint."""

    def __init__(self, timeout_seconds: int = 12) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                )
            }
        )

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        try:
            if os.getenv("SERPAPI_KEY"):
                return self._search_serpapi(query, limit)
            results = self._search_duckduckgo(query, limit)
            return results or self._search_bing(query, limit)
        except requests.RequestException as error:
            LOGGER.warning("Search failed for %r: %s", query, error)
            return []
        except (TypeError, ValueError) as error:
            LOGGER.warning("Search response could not be read for %r: %s", query, error)
            return []

    def fetch_text(self, url: str, max_chars: int = 30_000) -> str:
        """Fetch publicly available page text. Failures are intentionally non-fatal."""
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException:
            return ""

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return ""
        text = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", response.text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        return html.unescape(re.sub(r"\s+", " ", text)).strip()[:max_chars]

    def _search_serpapi(self, query: str, limit: int) -> list[SearchResult]:
        response = self.session.get(
            "https://serpapi.com/search.json",
            params={"q": query, "api_key": os.environ["SERPAPI_KEY"], "engine": "google"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        results = []
        for item in payload.get("organic_results", [])[:limit]:
            url = item.get("link", "")
            if url:
                results.append(SearchResult(item.get("title", ""), url, item.get("snippet", "")))
        return results

    def _search_duckduckgo(self, query: str, limit: int) -> list[SearchResult]:
        response = self.session.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        page = response.text
        links = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, flags=re.I | re.S
        )
        snippets = re.findall(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', page, flags=re.I | re.S
        )
        results: list[SearchResult] = []
        for index, (href, title_html) in enumerate(links[:limit]):
            url = self._unwrap_duckduckgo_url(html.unescape(href))
            if not url.startswith(("https://", "http://")):
                continue
            title = self._strip_html(title_html)
            snippet = self._strip_html(snippets[index]) if index < len(snippets) else ""
            results.append(SearchResult(title, url, snippet))
        return results

    def _search_bing(self, query: str, limit: int) -> list[SearchResult]:
        """Fallback for environments where DuckDuckGo's HTML endpoint is rate-limited."""
        response = self.session.get(
            "https://www.bing.com/search",
            params={"q": query},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        results: list[SearchResult] = []
        blocks = re.findall(r'<li[^>]+class="b_algo".*?</li>', response.text, flags=re.I | re.S)
        for block in blocks[:limit]:
            match = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
            if not match:
                continue
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
            results.append(
                SearchResult(
                    self._strip_html(match.group(2)),
                    html.unescape(match.group(1)),
                    self._strip_html(snippet_match.group(1)) if snippet_match else "",
                )
            )
        return results

    @staticmethod
    def _unwrap_duckduckgo_url(value: str) -> str:
        parsed = urlparse(value)
        if "duckduckgo.com" in parsed.netloc:
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(target)
        return value

    @staticmethod
    def _strip_html(value: str) -> str:
        return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value))).strip()
