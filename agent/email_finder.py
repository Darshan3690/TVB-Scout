"""Evidence-based founder-email validation. Never generates addresses."""

from __future__ import annotations

import re

from utils.sources import normalize_domain

GENERIC_LOCAL_PARTS = {"info", "hello", "contact", "support", "sales", "team", "admin", "office"}
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def is_verified_founder_email(
    email: str,
    founder_name: str,
    company_website: str,
    evidence_text: str,
) -> bool:
    """Require public evidence tying a non-generic company-domain address to the founder."""
    if not email or not founder_name or not evidence_text:
        return False
    match = EMAIL_PATTERN.fullmatch(email.strip())
    if not match:
        return False
    local_part, domain = email.lower().split("@", 1)
    if local_part in GENERIC_LOCAL_PARTS:
        return False
    company_domain = normalize_domain(company_website)
    if not company_domain or domain != company_domain:
        return False
    compact_evidence = evidence_text.lower()
    name_parts = [part.lower() for part in re.findall(r"[A-Za-z]+", founder_name) if len(part) > 1]
    return email.lower() in compact_evidence and all(part in compact_evidence for part in name_parts)


def find_public_founder_email(
    evidence_text: str,
    founder_name: str,
    company_website: str,
) -> str:
    for email in EMAIL_PATTERN.findall(evidence_text):
        if is_verified_founder_email(email, founder_name, company_website, evidence_text):
            return email
    return ""

