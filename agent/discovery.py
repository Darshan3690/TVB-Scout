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
FUNDING_TERMS = ("seed round", "seed funding", "pre-seed", "raised $1M", "raised $2M", "raised $3M", "Series Seed")


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
            r"^(.{2,60}?)\s+(?:raises?|raised|secures?|secured|lands?|landed|bags?|bagged|closes?|closed)\b",
            title,
            re.I,
        )
        if funding_match:
            candidate = funding_match.group(1).strip(" -:|")
            if not any(stop in candidate.lower() for stop in ("how ", "why ", "what ", "here are", "report", "news")):
                name = candidate
            else:
                name = ""
        else:
            # Filter out common junk titles
            junk_terms = (
                "top ", "list of", "startups funded", "market trends", "directory", "boom",
                "how to", "report", "roundup", "grant", "financing", "overview", "guide",
                "landscape", "here are", "biggest", "tracker", "funding in", "venture capital in",
                "top 10", "trends", "news", "explained", "analysis", "podcast", "episode",
                "ecosystem", "outlook", "hub", "biggest ai startups",
            )
            lower = title.lower()
            if any(term in lower for term in junk_terms):
                return ""

            for separator in (" | ", " - ", " -", ":"):
                if separator in title:
                    title = title.split(separator, 1)[0]
                    break
            name = title.strip()

        # Reject long sentences or non-company names
        if len(name.split()) > 4 or len(name) > 35 or len(name) < 2:
            return ""
        # Reject VC funds, accelerators, and ecosystem lists
        non_company_words = {
            "funding", "startup", "startups", "investors", "investing", "market",
            "india's", "africa's", "europe's", "billion", "million", "fund", "funds",
            "venture", "ventures", "capital", "accelerator", "incubator", "lab", "labs",
            "partners", "vc", "holdings", "group"
        }
        tokens = {w.lower().strip(".,'\"") for w in name.split()}
        if tokens & non_company_words:
            return ""
        return name
