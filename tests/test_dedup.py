from agent.dedup import deduplicate_companies
from models.company import Company


def test_deduplicates_domain_variants_and_keeps_discovery_sources():
    candidates = [
        Company(company_name="Example", website="https://example.com", discovery_sources=[{"type": "web"}]),
        Company(company_name="Example Technologies", website="http://www.example.com/about", discovery_sources=[{"type": "github"}], github_url="https://github.com/example/repo"),
    ]
    results = deduplicate_companies(candidates)
    assert len(results) == 1
    assert {source["type"] for source in results[0].discovery_sources} == {"web", "github"}
    assert results[0].github_url == "https://github.com/example/repo"


def test_falls_back_to_normalized_name_without_company_domain():
    candidates = [Company(company_name="Acme AI"), Company(company_name="Acme AI Inc.")]
    assert len(deduplicate_companies(candidates)) == 1

