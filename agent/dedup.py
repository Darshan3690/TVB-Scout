"""Candidate de-duplication before expensive research."""

from __future__ import annotations

from models.company import Company
from utils.sources import normalize_domain, normalize_name


def candidate_key(company: Company) -> str:
    domain = normalize_domain(company.website)
    # GitHub is a source, not a company domain, so it is never the primary key.
    if domain and domain != "github.com":
        return f"domain:{domain}"
    return f"name:{normalize_name(company.company_name)}"


def deduplicate_companies(candidates: list[Company]) -> list[Company]:
    unique: dict[str, Company] = {}
    for candidate in candidates:
        key = candidate_key(candidate)
        if key in {"name:", "domain:"}:
            continue
        existing = unique.get(key)
        if not existing:
            unique[key] = candidate
            continue

        existing.discovery_sources.extend(candidate.discovery_sources)
        if not existing.website and candidate.website:
            existing.website = candidate.website
        if not existing.description and candidate.description:
            existing.description = candidate.description
        if not existing.github_url and candidate.github_url:
            existing.github_url = candidate.github_url
            existing.github_stars = candidate.github_stars
            existing.open_source = candidate.open_source
        if not existing.source_url and candidate.source_url:
            existing.source_url = candidate.source_url
    return list(unique.values())

