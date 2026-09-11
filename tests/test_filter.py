from agent.filter import classify, passes_filters
from models.company import Company


def verified_company(**overrides):
    values = {
        "company_name": "Example",
        "funding_usd": 2_500_000,
        "funding_verified": True,
        "tech_verified": True,
        "us_presence_verified": True,
        "founder_name": "Jane Doe",
        "founder_role": "Founder & CEO",
        "founder_email": "jane@example.com",
        "email_verified": True,
        "source_url": "https://example.com/news",
    }
    values.update(overrides)
    return Company(**values)


def test_funding_bounds_are_strict():
    for amount, expected in ((500_000, False), (1_000_000, True), (2_500_000, True), (5_000_000, True), (5_000_001, False), (None, False)):
        company = verified_company(funding_usd=amount, funding_verified=amount is not None)
        assert passes_filters(company)[0] is expected


def test_missing_email_is_rejected():
    company = verified_company(founder_email="", email_verified=False)
    assert passes_filters(company) == (False, "Founder email could not be verified")


def test_classify_preserves_rejection_reason():
    company = classify(verified_company(tech_verified=False))
    assert company.qualified is False
    assert company.rejection_reason == "Technology platform could not be verified"

