from agent.email_finder import find_public_founder_email, is_verified_founder_email


def test_accepts_public_company_domain_email_tied_to_founder():
    evidence = "Jane Doe, Founder & CEO. Reach Jane at jane@example.com for media requests."
    assert is_verified_founder_email("jane@example.com", "Jane Doe", "https://example.com", evidence)
    assert find_public_founder_email(evidence, "Jane Doe", "https://example.com") == "jane@example.com"


def test_rejects_generic_and_inferred_email():
    evidence = "Jane Doe is the founder. Contact info@example.com."
    assert not is_verified_founder_email("info@example.com", "Jane Doe", "https://example.com", evidence)
    assert not is_verified_founder_email("jane@example.com", "Jane Doe", "https://example.com", "Jane Doe is founder")

