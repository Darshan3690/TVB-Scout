"""Clean JSON-first search client supporting Serper.dev, Tavily, and SerpAPI."""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.logging import get_logger

LOGGER = get_logger("SEARCH")


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


def _make_session(timeout_seconds: int) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


class SearchClient:
    """Primary search backend: Serper.dev / Tavily / SerpAPI, with keyless fallback."""

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = _make_session(timeout_seconds)

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        # 1. Serper.dev (Google Search API in JSON)
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            try:
                return self._search_serper(query, serper_key, limit)
            except Exception as error:
                LOGGER.warning("Serper failed for %r: %s", query, error)
                return []

        # 2. Tavily Search API
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                results = self._search_tavily(query, tavily_key, limit)
                if results:
                    return results
            except Exception as error:
                LOGGER.warning("Tavily failed for %r: %s", query, error)

        # 3. SerpAPI (if configured and has quota)
        serpapi_key = os.getenv("SERPAPI_KEY")
        if serpapi_key:
            try:
                results = self._search_serpapi(query, serpapi_key, limit)
                if results:
                    return results
            except Exception as error:
                LOGGER.warning("SerpAPI failed for %r: %s", query, error)

        # 4. Keyless DuckDuckGo / Bing fallback
        try:
            results = self._search_duckduckgo(query, limit)
            if results:
                return results
        except Exception:
            pass

        try:
            return self._search_bing(query, limit)
        except Exception:
            return []

    def _search_serper(self, query: str, api_key: str, limit: int) -> list[SearchResult]:
        import time
        for attempt in range(3):
            resp = self.session.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": min(limit, 10)},
                timeout=self.timeout_seconds,
            )
            if resp.status_code == 429:
                time.sleep(1.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            results: list[SearchResult] = []
            for item in data.get("organic", [])[:limit]:
                link = item.get("link", "")
                if link and link.startswith(("http://", "https://")):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=link,
                            snippet=item.get("snippet", ""),
                        )
                    )
            return results
        return []

    def _search_tavily(self, query: str, api_key: str, limit: int) -> list[SearchResult]:
        resp = self.session.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": min(limit, 10)},
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            url = item.get("url", "")
            if url and url.startswith(("http://", "https://")):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=url,
                        snippet=item.get("content", "")[:300],
                    )
                )
        return results

    def _search_serpapi(self, query: str, api_key: str, limit: int) -> list[SearchResult]:
        resp = self.session.get(
            "https://serpapi.com/search.json",
            params={"q": query, "api_key": api_key, "engine": "google"},
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        payload = resp.json()
        results = []
        for item in payload.get("organic_results", [])[:limit]:
            url = item.get("link", "")
            if url:
                results.append(SearchResult(item.get("title", ""), url, item.get("snippet", "")))
        return results

    def _search_duckduckgo(self, query: str, limit: int) -> list[SearchResult]:
        clean_q = re.sub(r'\bOR\b', '', query).strip()
        resp = self.session.post(
            "https://html.duckduckgo.com/html/",
            data={"q": clean_q},
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        links = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text, flags=re.I | re.S
        )
        snippets = re.findall(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', resp.text, flags=re.I | re.S
        )
        results: list[SearchResult] = []
        for index, (href, title_html) in enumerate(links[:limit]):
            url = html.unescape(href)
            if "duckduckgo.com" in url:
                target = parse_qs(urlparse(url).query).get("uddg", [""])[0]
                url = unquote(target)
            if not url.startswith(("https://", "http://")):
                continue
            title = self._strip_html(title_html)
            snippet = self._strip_html(snippets[index]) if index < len(snippets) else ""
            results.append(SearchResult(title, url, snippet))
        return results

    def _search_bing(self, query: str, limit: int) -> list[SearchResult]:
        clean_q = re.sub(r'\bOR\b', '', query).strip()
        resp = self.session.get(
            "https://www.bing.com/search",
            params={"q": clean_q, "setlang": "en-US", "cc": "US", "count": min(limit, 10)},
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        blocks = re.findall(r'<li[^>]+class="[^"]*b_algo[^"]*".*?</li>', resp.text, flags=re.I | re.S)
        results: list[SearchResult] = []
        for block in blocks[:limit]:
            href_m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
            if not href_m:
                continue
            raw_url = html.unescape(href_m.group(1))
            real_url = self._unwrap_bing_url(raw_url)
            if not real_url.startswith(("http://", "https://")):
                continue
            title = self._strip_html(href_m.group(2))
            snip_m = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
            snippet = self._strip_html(snip_m.group(1)) if snip_m else ""
            results.append(SearchResult(title, real_url, snippet))
        return results

    @staticmethod
    def _unwrap_bing_url(value: str) -> str:
        value = html.unescape(value)
        if "bing.com/ck/a" in value or "bing.com/ck/" in value:
            parsed = urlparse(value)
            params = parse_qs(parsed.query)
            target = params.get("u", params.get("url", [""]))[0]
            if target:
                try:
                    import base64
                    if target.startswith("a1"):
                        payload = target[2:]
                        padded = payload + "=" * ((4 - len(payload) % 4) % 4)
                        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                        if decoded.startswith(("http://", "https://")):
                            return decoded
                except Exception:
                    pass
                if target.startswith(("http", "%")):
                    return unquote(target)
        return value

    @staticmethod
    def _strip_html(value: str) -> str:
        return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value))).strip()

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
