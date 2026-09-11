"""Deterministic final qualification rules."""

from __future__ import annotations

from models.company import Company

MIN_FUNDING_USD = 1_000_000
MAX_FUNDING_USD = 5_000_000


def passes_filters(company: Company) -> tuple[bool, str]:
    if not company.funding_verified or company.funding_usd is None:
        return False, "Funding could not be verified"
    if not MIN_FUNDING_USD <= company.funding_usd <= MAX_FUNDING_USD:
        return False, "Funding outside $1M-$5M"
    if not company.tech_verified:
        return False, "Technology platform could not be verified"
    if not company.us_presence_verified:
        return False, "US presence could not be verified"
    if not company.founder_name or not company.founder_role:
        return False, "CEO/co-founder could not be identified"
    if not company.email_verified or not company.founder_email:
        return False, "Founder email could not be verified"
    if not company.source_url:
        return False, "Useful source URL could not be verified"
    return True, ""


def classify(company: Company) -> Company:
    company.qualified, company.rejection_reason = passes_filters(company)
    return company

