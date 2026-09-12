"""Public web-search adapter with optional SerpAPI support."""

from __future__ import annotations

import html
import os
import re
import time
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
    """Uses SerpAPI when configured, otherwise tries DuckDuckGo then Bing."""

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = _make_session(timeout_seconds)

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        if os.getenv("SERPAPI_KEY"):
            try:
                return self._search_serpapi(query, limit)
            except (requests.RequestException, ValueError, TypeError) as error:
                LOGGER.warning("SerpAPI failed for %r: %s", query, error)
                return []

        # Try DuckDuckGo first, then Bing — each engine in its own try block so
        # a DDG timeout does NOT swallow the Bing fallback.
        ddg_results: list[SearchResult] = []
        try:
            ddg_results = self._search_duckduckgo(query, limit)
        except (requests.RequestException, ValueError, TypeError) as error:
            LOGGER.warning("DDG failed for %r: %s", query, error)

        if ddg_results:
            return ddg_results

        try:
            return self._search_bing(query, limit)
        except (requests.RequestException, ValueError, TypeError) as error:
            LOGGER.warning("Bing failed for %r: %s", query, error)
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
        import time
        last_error: Exception | None = None
        for attempt in range(3):  # up to 3 attempts on timeout
            try:
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
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
                last_error = e
                LOGGER.warning("SerpAPI timeout (attempt %d/3) for %r — retrying in 2s", attempt + 1, query)
                time.sleep(2)
            except (requests.RequestException, ValueError, TypeError) as e:
                raise  # non-timeout errors propagate immediately
        raise last_error  # type: ignore[misc]

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
        """Primary keyless fallback. Parses multiple Bing result block formats."""
        response = self.session.get(
            "https://www.bing.com/search",
            params={"q": query, "count": min(limit, 10)},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        page = response.text
        results: list[SearchResult] = []

        # Bing wraps result URLs in a /ck/a redirect — unwrap to get real URL
        # Also try multiple element patterns as Bing markup varies by region/version
        blocks = re.findall(r'<li[^>]+class="[^"]*b_algo[^"]*".*?</li>', page, flags=re.I | re.S)
        if not blocks:
            LOGGER.warning("Bing returned no b_algo blocks for %r (possible CAPTCHA/redirect)", query)
            return []

        for block in blocks[:limit]:
            href_match = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
            if not href_match:
                href_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
            if not href_match:
                continue
            raw_url = html.unescape(href_match.group(1))
            real_url = self._unwrap_bing_url(raw_url)
            if not real_url.startswith(("http://", "https://")):
                continue
            title = self._strip_html(href_match.group(2))
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
            if not snippet_match:
                snippet_match = re.search(r'<div[^>]+class="[^"]*b_caption[^"]*"[^>]*>(.*?)</div>', block, flags=re.I | re.S)
            snippet = self._strip_html(snippet_match.group(1)) if snippet_match else ""
            results.append(SearchResult(title, real_url, snippet))

        return results

    @staticmethod
    def _unwrap_bing_url(value: str) -> str:
        """Extract the real destination from a bing.com/ck/a redirect link."""
        if "bing.com/ck/a" in value or "bing.com/ck/" in value:
            parsed = urlparse(value)
            # &u= contains a base64url-like encoded real URL
            params = parse_qs(parsed.query)
            target = params.get("u", params.get("url", [""]))[0]
            if target:
                # Bing uses a modified base64 without padding starting with 'a1'
                try:
                    import base64
                    if target.startswith("a1"):
                        padded = target[2:] + "==="
                        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                        if decoded.startswith(("http://", "https://")):
                            return decoded
                except Exception:  # noqa: BLE001
                    pass
                if target.startswith(("http", "%")):
                    return unquote(target)
        return value

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
