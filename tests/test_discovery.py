from agent.discovery import WebDiscovery
from utils.search import SearchClient


def test_extracts_company_name_from_funding_headline():
    assert WebDiscovery._candidate_name("Acme AI Raises $2.4M to expand its platform") == "Acme AI"


def test_ignores_generic_directory_headlines():
    assert WebDiscovery._candidate_name("Top B2B SaaS Startups in India") == ""


def test_generates_varied_queries_between_rounds():
    discovery = WebDiscovery(SearchClient())
    assert discovery.generate_queries(0, limit=2) != discovery.generate_queries(1, limit=2)
