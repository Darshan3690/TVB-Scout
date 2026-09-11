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

        merge_company_records(existing, candidate)
    return list(unique.values())


def merge_company_records(primary: Company, duplicate: Company) -> Company:
    """Keep the first record while retaining useful discovery metadata from a duplicate."""
    for source in duplicate.discovery_sources:
        if source not in primary.discovery_sources:
            primary.discovery_sources.append(source)
    if not primary.website and duplicate.website:
        primary.website = duplicate.website
    if not primary.description and duplicate.description:
        primary.description = duplicate.description
    if not primary.github_url and duplicate.github_url:
        primary.github_url = duplicate.github_url
        primary.github_stars = duplicate.github_stars
        primary.open_source = duplicate.open_source
    if not primary.source_url and duplicate.source_url:
        primary.source_url = duplicate.source_url
    return primary
