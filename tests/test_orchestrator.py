from agent.orchestrator import ScoutOrchestrator
from models.company import Company


class StaticDiscovery:
    def __init__(self, candidates):
        self.candidates = candidates

    def discover(self, _round_index):
        return self.candidates


class EmptyDiscovery:
    def discover(self, _round_index):
        return []


class SameDomainResearcher:
    def research(self, company):
        company.website = "https://example.com"
        company.funding_usd = 2_000_000
        company.funding_verified = True
        company.tech_verified = True
        company.us_presence_verified = True
        company.founder_name = "Jane Doe"
        company.founder_role = "Founder & CEO"
        company.founder_email = "jane@example.com"
        company.email_verified = True
        return company


def test_post_research_deduplication_uses_resolved_company_domain():
    run = ScoutOrchestrator(
        web_discovery=StaticDiscovery(
            [
                Company(company_name="Example AI", source_url="https://news.one/example"),
                Company(company_name="Example Technologies", source_url="https://news.two/example"),
            ]
        ),
        github_discovery=EmptyDiscovery(),
        researcher=SameDomainResearcher(),
    ).run(target_leads=2, max_discovery_rounds=1, max_candidates_per_round=2)

    assert len(run.qualified_leads) == 1
    assert run.unique_companies == 1
    assert any("Post-research duplicate" in message for message in run.activity)
