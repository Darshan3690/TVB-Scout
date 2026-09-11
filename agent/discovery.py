"""Dynamic web discovery; no company names are stored in this module."""

from __future__ import annotations

import re
from itertools import product

from models.company import Company
from utils.search import SearchClient
from utils.sources import is_http_url

TECH_TERMS = (
    "AI platform",
    "B2B SaaS",
    "developer tools",
    "fintech platform",
    "data platform",
    "automation platform",
    "cloud infrastructure",
    "machine learning platform",
)
GEOGRAPHIES = ("India", "Africa", "Europe", "Southeast Asia", "Latin America", "Middle East")
FUNDING_TERMS = ("raised funding", "seed round", "venture funding", "investment")


class WebDiscovery:
    def __init__(self, search: SearchClient) -> None:
        self.search = search

    def generate_queries(self, round_index: int, limit: int = 6) -> list[str]:
        combinations = [f"{tech} startup {funding} {geography}" for tech, geography, funding in product(TECH_TERMS, GEOGRAPHIES, FUNDING_TERMS)]
        start = (round_index * limit) % len(combinations)
        return [combinations[(start + offset) % len(combinations)] for offset in range(limit)]

    def discover(self, round_index: int, query_limit: int = 6) -> list[Company]:
        candidates: list[Company] = []
        for query in self.generate_queries(round_index, query_limit):
            for result in self.search.search(query):
                if not is_http_url(result.url):
                    continue
                name = self._candidate_name(result.title)
                if not name:
                    continue
                candidates.append(
                    Company(
                        company_name=name,
                        description=result.snippet,
                        # A press article is discovery evidence, not proof that its host is the company site.
                        website="",
                        source_url=result.url,
                        discovery_sources=[{"type": "web", "url": result.url, "query": query}],
                    )
                )
        return candidates

    @staticmethod
    def _candidate_name(title: str) -> str:
        title = title.strip()
        funding_match = re.search(
            r"^(.{2,100}?)\s+(?:raises?|raised|secures?|secured|lands?|landed|bags?|bagged|closes?|closed)\b",
            title,
            re.I,
        )
        if funding_match:
            return funding_match.group(1).strip(" -:|")
        if any(term in title.lower() for term in ("top ", "list of", "startups funded", "market trends", "directory")):
            return ""
        for separator in (" | ", " - ", " -", ":"):
            if separator in title:
                title = title.split(separator, 1)[0]
                break
        return title.strip()[:120]
