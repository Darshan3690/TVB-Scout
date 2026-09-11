"""Evidence-first public research for a discovered candidate."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agent.email_finder import find_public_founder_email
from agent.llm import EvidenceExtractor
from models.company import Company
from utils.search import SearchClient, SearchResult
from utils.sources import normalize_domain

MONEY_PATTERN = re.compile(
    r"(?P<prefix>US\$|USD\s?|\$)\s?(?P<amount>\d+(?:\.\d+)?)\s?(?P<unit>[kKmMbB]|million|mn|billion|bn)?",
    re.IGNORECASE,
)
FOUNDER_PATTERN = re.compile(
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:,|[-|])?\s*(?P<role>Founder(?:\s*&\s*CEO)?|Co-founder(?:\s*&\s*CEO)?|CEO|Founder and CEO)",
)


@dataclass(frozen=True)
class Evidence:
    text: str
    url: str


class Researcher:
    def __init__(self, search: SearchClient, extractor: EvidenceExtractor | None = None) -> None:
        self.search = search
        self.extractor = extractor or EvidenceExtractor()

    def research(self, company: Company) -> Company:
        """Enrich one candidate. Every positive verification includes a public source URL."""
        name = company.company_name
        if not company.website:
            company.website = self._resolve_official_website(name)
        website_text = self.search.fetch_text(company.website) if company.website else ""
        if website_text and not company.description:
            company.description = website_text[:500]

        funding = self._evidence(name, "funding OR raised OR investment")
        self._apply_funding(company, funding)

        tech = Evidence(website_text, company.website) if website_text else self._first_evidence(name, "platform software SaaS technology")
        self._apply_technology(company, tech)

        us_presence = self._evidence(name, '"United States" OR USA OR "US office" headquarters')
        self._apply_us_presence(company, us_presence)

        founder = self._evidence(name, 'CEO OR founder OR "co-founder"')
        self._apply_founder(company, founder)

        self._apply_llm_hints(company, tech, founder, us_presence)

        if company.founder_name and company.website:
            email = self._evidence(f'"{company.founder_name}"', f'"@{normalize_domain(company.website)}" email')
            self._apply_email(company, email)
        return company

    def _apply_llm_hints(
        self,
        company: Company,
        tech: Evidence,
        founder_evidence: list[Evidence],
        us_evidence: list[Evidence],
    ) -> None:
        """LLM values are hints and still need direct evidence before setting a verified field."""
        evidence = "\n".join(
            item.text for item in [tech, *founder_evidence, *us_evidence] if item.text
        )
        hints = self.extractor.extract(company.company_name, evidence)
        if not company.description and hints.get("description"):
            company.description = hints["description"]
        if not company.industry and hints.get("industry"):
            company.industry = hints["industry"]
        if not company.us_presence and hints.get("us_presence_summary"):
            company.us_presence = hints["us_presence_summary"]
        if company.founder_name or not hints.get("founder_name"):
            return

        hinted_name = hints["founder_name"]
        hinted_role = hints.get("founder_role", "")
        if hinted_role not in {"CEO", "Founder", "Co-founder", "Founder & CEO", "Co-founder & CEO"}:
            return
        name_tokens = re.findall(r"[A-Za-z]+", hinted_name.lower())
        for item in founder_evidence:
            lower_evidence = item.text.lower()
            if name_tokens and all(token in lower_evidence for token in name_tokens) and hinted_role.lower() in lower_evidence:
                company.founder_name = hinted_name
                company.founder_role = hinted_role
                company.founder_source = item.url
                return

    def _resolve_official_website(self, company_name: str) -> str:
        """Find a likely first-party site without treating a directory as company evidence."""
        excluded_domains = {
            "github.com", "linkedin.com", "crunchbase.com", "tracxn.com", "facebook.com",
            "instagram.com", "x.com", "twitter.com", "wikipedia.org",
        }
        name_tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9]+", company_name) if len(token) > 2}
        for result in self.search.search(f'"{company_name}" official website', limit=5):
            domain = normalize_domain(result.url)
            if not domain or domain in excluded_domains:
                continue
            title = result.title.lower()
            if name_tokens and any(token in title or token in domain for token in name_tokens):
                return result.url
        return ""

    def _evidence(self, subject: str, qualifier: str) -> list[Evidence]:
        return [Evidence(f"{result.title}. {result.snippet}", result.url) for result in self.search.search(f'"{subject}" {qualifier}', limit=6)]

    def _first_evidence(self, subject: str, qualifier: str) -> Evidence:
        evidence = self._evidence(subject, qualifier)
        return evidence[0] if evidence else Evidence("", "")

    def _apply_funding(self, company: Company, evidence: list[Evidence]) -> None:
        for item in evidence:
            text = item.text
            if not re.search(r"\b(raised|funding|investment|seed|revenue)\b", text, re.I):
                continue
            amount = self._extract_usd(text)
            if amount is not None:
                company.funding_usd = amount
                company.funding_or_revenue = self._extract_money_label(text)
                company.funding_verified = True
                company.funding_source = item.url
                return

    def _apply_technology(self, company: Company, evidence: Evidence) -> None:
        if not evidence.text:
            return
        match = re.search(
            r"\b(AI|artificial intelligence|SaaS|developer|fintech|data|automation|cloud|machine learning|software)\b[^.]{0,120}\b(platform|software|infrastructure|tool)\b",
            evidence.text,
            re.I,
        )
        if match:
            company.tech_platform = match.group(0).strip()
            company.tech_verified = True
            company.tech_source = evidence.url
            if not company.industry:
                company.industry = match.group(1).title()

    def _apply_us_presence(self, company: Company, evidence: list[Evidence]) -> None:
        """Only accept affirmative evidence; absence of US results is not evidence of absence."""
        for item in evidence:
            normalized = item.text.lower()
            if re.search(r"\b(no|without|does not have|doesn't have)\b.{0,45}\b(united states|usa|u\.s\.|us office)\b", normalized):
                company.us_presence = "Public source states no US presence"
                company.us_presence_verified = True
                company.us_presence_source = item.url
                return
            if re.search(r"\b(exclusively|only)\b.{0,45}\b(india|africa|europe|asia|latin america|middle east)\b", normalized):
                company.us_presence = "Public source describes operations as outside the US"
                company.us_presence_verified = True
                company.us_presence_source = item.url
                return
            if re.search(r"\b(united states|usa|u\.s\.|us office|new york|san francisco)\b", normalized):
                company.us_presence = "US presence reported"
                company.us_presence_source = item.url
                return

    def _apply_founder(self, company: Company, evidence: list[Evidence]) -> None:
        for item in evidence:
            match = FOUNDER_PATTERN.search(item.text)
            if match:
                company.founder_name = match.group("name")
                company.founder_role = match.group("role")
                company.founder_source = item.url
                return

    def _apply_email(self, company: Company, evidence: list[Evidence]) -> None:
        for item in evidence:
            email = find_public_founder_email(item.text, company.founder_name, company.website)
            if email:
                company.founder_email = email
                company.email_verified = True
                company.email_source = item.url
                return

    @staticmethod
    def _extract_usd(text: str) -> float | None:
        match = MONEY_PATTERN.search(text)
        if not match:
            return None
        amount = float(match.group("amount"))
        unit = (match.group("unit") or "").lower()
        multiplier = {"k": 1_000, "m": 1_000_000, "million": 1_000_000, "mn": 1_000_000, "b": 1_000_000_000, "billion": 1_000_000_000, "bn": 1_000_000_000}.get(unit, 1)
        return amount * multiplier

    @staticmethod
    def _extract_money_label(text: str) -> str:
        match = MONEY_PATTERN.search(text)
        return match.group(0).strip() if match else ""
