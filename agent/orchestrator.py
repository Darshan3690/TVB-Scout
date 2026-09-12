"""The single orchestration point for TVB Scout."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from agent.dedup import candidate_key, deduplicate_companies, merge_company_records
from agent.discovery import WebDiscovery
from agent.filter import classify
from agent.github_discovery import GitHubDiscovery
from agent.research import Researcher
from models.company import Company
from utils.search import SearchClient
from utils.sources import normalize_domain, normalize_name

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
    def __init__(
        self,
        event_callback: EventCallback | None = None,
        web_discovery: WebDiscovery | None = None,
        github_discovery: GitHubDiscovery | None = None,
        researcher: Researcher | None = None,
    ) -> None:
        search = SearchClient() if not (web_discovery and researcher) else None
        self.web_discovery = web_discovery or WebDiscovery(search or SearchClient())
        self.github_discovery = github_discovery or GitHubDiscovery()
        self.researcher = researcher or Researcher(search or SearchClient())
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
        result_by_key: dict[str, Company] = {}

        for round_index in range(max_discovery_rounds):
            if len(run.qualified_leads) >= target_leads:
                break
            self._emit(run, f"[DISCOVERY] Round {round_index + 1}/{max_discovery_rounds}")

            # Run web + github discovery concurrently
            with ThreadPoolExecutor(max_workers=2) as disc_pool:
                f_web = disc_pool.submit(self.web_discovery.discover, round_index)
                f_gh  = disc_pool.submit(self.github_discovery.discover, round_index)
                web    = f_web.result()
                github = f_gh.result()

            run.web_candidates += len(web)
            run.github_candidates += len(github)
            self._emit(run, f"[DISCOVERY] Web candidates: +{len(web)} | GitHub candidates: +{len(github)}")

            all_candidates.extend(web + github)
            unique_candidates = deduplicate_companies(all_candidates)
            run.unique_companies = len(unique_candidates)
            self._emit(run, f"[DEDUP] Unique companies: {run.unique_companies}")

            # Build this round's research batch (unprocessed candidates only)
            to_research: list[Company] = []
            for candidate in unique_candidates:
                name_k = f"name:{normalize_name(candidate.company_name)}"
                domain_k = f"domain:{normalize_domain(candidate.website)}" if candidate.website else ""
                if name_k in processed_keys or (domain_k and domain_k in processed_keys):
                    continue
                processed_keys.add(name_k)
                if domain_k:
                    processed_keys.add(domain_k)
                to_research.append(candidate)
                if len(to_research) >= max_candidates_per_round:
                    self._emit(run, f"[RESEARCH] Round budget reached ({max_candidates_per_round} companies)")
                    break

            if not to_research:
                continue

            self._emit(run, f"[RESEARCH] Researching {len(to_research)} companies in parallel (3 workers)")

            def _safe_research(candidate: Company) -> Company:
                try:
                    return self.researcher.research(candidate)
                except Exception as error:  # noqa: BLE001
                    candidate.rejection_reason = f"Research failed: {type(error).__name__}"
                    return candidate

            # Research up to 3 companies concurrently, then process results sequentially
            researched_batch: list[Company] = [None] * len(to_research)  # type: ignore[list-item]
            with ThreadPoolExecutor(max_workers=3) as res_pool:
                future_to_idx = {res_pool.submit(_safe_research, c): i for i, c in enumerate(to_research)}
                for future in as_completed(future_to_idx):
                    researched_batch[future_to_idx[future]] = future.result()

            # Process results in main thread (keeps _emit and list mutations thread-safe)
            for researched in researched_batch:
                run.researched_companies += 1
                self._emit(run, f"[RESEARCH] Researching {researched.company_name}")
                self._emit(run, f"  funding_verified={researched.funding_verified}  usd={researched.funding_usd}  ({researched.funding_or_revenue})")
                self._emit(run, f"  tech_verified={researched.tech_verified}  ({researched.tech_platform[:60] if researched.tech_platform else '-'})")
                self._emit(run, f"  us_presence_verified={researched.us_presence_verified}  ({researched.us_presence[:60] if researched.us_presence else '-'})")
                self._emit(run, f"  founder={researched.founder_name!r}  role={researched.founder_role!r}")
                self._emit(run, f"  email_verified={researched.email_verified}  ({researched.founder_email or '-'})")

                resolved_key = candidate_key(researched)
                if existing := result_by_key.get(resolved_key):
                    merge_company_records(existing, researched)
                    self._emit(run, f"[DEDUP] Post-research duplicate: {researched.company_name}")
                    continue
                result_by_key[resolved_key] = researched
                if researched.website:
                    processed_keys.add(f"domain:{normalize_domain(researched.website)}")
                if researched.company_name:
                    processed_keys.add(f"name:{normalize_name(researched.company_name)}")
                classify(researched)
                if researched.qualified:
                    run.qualified_leads.append(researched)
                    self._emit(run, f"[FILTER] QUALIFIED: {researched.company_name}")
                else:
                    run.rejected_leads.append(researched)
                    self._emit(run, f"[FILTER] REJECTED: {researched.company_name} - {researched.rejection_reason}")
                if len(run.qualified_leads) >= target_leads:
                    break

        run.unique_companies = len(result_by_key)
        self._emit(run, f"[COMPLETE] {len(run.qualified_leads)} qualified leads found")
        return run

    def _emit(self, run: ScoutRun, message: str) -> None:
        run.activity.append(message)
        if self.event_callback:
            try:
                self.event_callback(message)
            except Exception:
                pass
