"""Normalized company record used across discovery, research, and export."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Company:
    company_name: str = ""
    description: str = ""
    industry: str = ""
    website: str = ""

    funding_or_revenue: str = ""
    funding_usd: float | None = None
    funding_verified: bool = False
    funding_source: str = ""

    tech_platform: str = ""
    tech_verified: bool = False
    tech_source: str = ""

    us_presence: str = ""
    us_presence_verified: bool = False
    us_presence_source: str = ""

    founder_name: str = ""
    founder_role: str = ""
    founder_email: str = ""
    email_verified: bool = False
    founder_source: str = ""
    email_source: str = ""

    github_url: str = ""
    github_stars: int = 0
    open_source: bool = False

    yc_backed: bool = False
    yc_source: str = ""

    discovery_sources: list[dict[str, Any]] = field(default_factory=list)
    source_url: str = ""

    qualified: bool = False
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

