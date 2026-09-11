"""URL and evidence helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_domain(value: str) -> str:
    """Return a stable host key, stripping protocol, www, ports, and paths."""
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def normalize_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\b(incorporated|inc|limited|ltd|llc|technologies|technology|company)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

