"""GitHub discovery adapter. Repository popularity is only a discovery signal."""

from __future__ import annotations

import os
from typing import Any

import requests

from models.company import Company
from utils.logging import get_logger

LOGGER = get_logger("GITHUB")
TOPICS = ("artificial-intelligence", "llm", "developer-tools", "automation", "fintech", "data-platform", "cloud", "machine-learning")


class GitHubDiscovery:
    def __init__(self, timeout_seconds: int = 12) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json", "User-Agent": "TVB-Scout"})
        if token := os.getenv("GITHUB_TOKEN"):
            self.session.headers["Authorization"] = f"Bearer {token}"

    def discover(self, round_index: int, topic_limit: int = 3, repos_per_topic: int = 8) -> list[Company]:
        candidates: list[Company] = []
        for offset in range(topic_limit):
            topic = TOPICS[(round_index * topic_limit + offset) % len(TOPICS)]
            try:
                response = self.session.get(
                    "https://api.github.com/search/repositories",
                    params={"q": f"topic:{topic} stars:>20 archived:false", "sort": "updated", "order": "desc", "per_page": repos_per_topic},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
            except (requests.RequestException, ValueError) as error:
                LOGGER.warning("Discovery failed for topic %s: %s", topic, error)
                continue
            for repo in payload.get("items", []):
                if repo.get("fork"):
                    continue
                repository_url = repo.get("html_url", "")
                homepage = (repo.get("homepage") or "").strip()
                name = repo.get("name") or repo.get("full_name", "")
                candidates.append(
                    Company(
                        company_name=name,
                        description=repo.get("description") or "",
                        website=homepage,
                        source_url=repository_url,
                        github_url=repository_url,
                        github_stars=int(repo.get("stargazers_count") or 0),
                        open_source=True,
                        discovery_sources=[
                            {"type": "github", "url": repository_url, "stars": int(repo.get("stargazers_count") or 0), "topic": topic}
                        ],
                    )
                )
        return candidates

