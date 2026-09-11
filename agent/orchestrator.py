"""The single orchestration point for TVB Scout."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agent.dedup import deduplicate_companies
from agent.discovery import WebDiscovery
from agent.filter import classify
from agent.github_discovery import GitHubDiscovery
from agent.research import Researcher
from models.company import Company
from utils.search import SearchClient

EventCallback = Callable[[str], None]


@dataclass
class ScoutRun:
    qualified_leads: list[Company] = field(default_factory=list)
    rejected_leads: list[Company] = field(default_factory=list)
    activity: list[str] = field(default_factory=list)
    web_candidates: int = 0
    github_candidates: int = 0
    unique_companies: int = 0
    researched_companies: int = 0

    @property
    def verified_emails(self) -> int:
        return sum(lead.email_verified for lead in self.qualified_leads + self.rejected_leads)


class ScoutOrchestrator:
    def __init__(self, event_callback: EventCallback | None = None) -> None:
        search = SearchClient()
        self.web_discovery = WebDiscovery(search)
        self.github_discovery = GitHubDiscovery()
        self.researcher = Researcher(search)
        self.event_callback = event_callback

    def run(
        self,
        target_leads: int = 15,
        max_discovery_rounds: int = 5,
        max_candidates_per_round: int = 8,
    ) -> ScoutRun:
        run = ScoutRun()
        all_candidates: list[Company] = []
        processed_keys: set[str] = set()

        for round_index in range(max_discovery_rounds):
            if len(run.qualified_leads) >= target_leads:
                break
            self._emit(run, f"[DISCOVERY] Round {round_index + 1}/{max_discovery_rounds}")
            web = self.web_discovery.discover(round_index)
            github = self.github_discovery.discover(round_index)
            run.web_candidates += len(web)
            run.github_candidates += len(github)
            self._emit(run, f"[DISCOVERY] Web candidates: +{len(web)} | GitHub candidates: +{len(github)}")

            all_candidates.extend(web + github)
            unique_candidates = deduplicate_companies(all_candidates)
            run.unique_companies = len(unique_candidates)
            self._emit(run, f"[DEDUP] Unique companies: {run.unique_companies}")

            round_researched = 0
            for candidate in unique_candidates:
                key = candidate.website or candidate.github_url or candidate.company_name.lower()
                if key in processed_keys:
                    continue
                if round_researched >= max_candidates_per_round:
                    self._emit(run, f"[RESEARCH] Round budget reached ({max_candidates_per_round} companies)")
                    break
                processed_keys.add(key)
                round_researched += 1
                self._emit(run, f"[RESEARCH] Researching {candidate.company_name}")
                try:
                    researched = self.researcher.research(candidate)
                except Exception as error:  # A candidate must never terminate the full run.
                    researched = candidate
                    researched.rejection_reason = f"Research failed: {type(error).__name__}"
                    self._emit(run, f"[RESEARCH] Failed safely for {candidate.company_name}")
                run.researched_companies += 1
                classify(researched)
                if researched.qualified:
                    run.qualified_leads.append(researched)
                    self._emit(run, f"[FILTER] QUALIFIED: {researched.company_name}")
                else:
                    run.rejected_leads.append(researched)
                    self._emit(run, f"[FILTER] REJECTED: {researched.company_name} - {researched.rejection_reason}")
                if len(run.qualified_leads) >= target_leads:
                    break

        self._emit(run, f"[COMPLETE] {len(run.qualified_leads)} qualified leads found")
        return run

    def _emit(self, run: ScoutRun, message: str) -> None:
        run.activity.append(message)
        if self.event_callback:
            self.event_callback(message)
