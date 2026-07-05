"""Tests for email finder (Hunter.io + fallbacks)."""

from __future__ import annotations

from unittest.mock import patch

from job_radar import email_finder


def test_emails_in_text_skips_junk():
    text = "Reach us at careers@acme.com or noreply@example.com"
    assert email_finder.emails_in_text(text) == ["careers@acme.com"]


def test_domain_from_job_url_skips_linkedin():
    assert email_finder.domain_from_job_url("https://www.linkedin.com/jobs/view/123") is None


def test_domain_from_job_url_company_site():
    assert email_finder.domain_from_job_url("https://www.razorpay.com/careers/role") == "razorpay.com"


def test_find_contact_email_from_description():
    email, source = email_finder.find_contact_email(
        "Acme",
        "Write to hiring@acme.com",
        use_hunter=False,
    )
    assert email == "hiring@acme.com"
    assert source == "description"


def test_find_contact_email_guess_fallback():
    email, source = email_finder.find_contact_email(
        "Acme Corp", use_hunter=False, allow_guess=True
    )
    assert email == "careers@acmecorp.com"
    assert source == "guess"


@patch("job_radar.email_finder.requests.get")
def test_hunter_domain_search(mock_get):
    mock_get.return_value.json.return_value = {
        "data": {
            "emails": [
                {"value": "ceo@stripe.com", "type": "personal", "confidence": 90},
                {"value": "careers@stripe.com", "type": "generic", "confidence": 85, "department": "hr"},
            ]
        }
    }
    mock_get.return_value.raise_for_status = lambda: None

    email = email_finder.hunter_domain_search(domain="stripe.com", api_key="test-key")
    assert email == "careers@stripe.com"


@patch("job_radar.email_finder.hunter_domain_search")
def test_find_contact_email_uses_hunter(mock_hunter):
    mock_hunter.return_value = "talent@infosys.com"
    email, source = email_finder.find_contact_email(
        "Infosys",
        job_url="https://www.linkedin.com/jobs/view/1",
        use_hunter=True,
    )
    assert email == "talent@infosys.com"
    assert source == "hunter"
    mock_hunter.assert_called_with(domain=None, company="Infosys")


def test_classify_audience():
    assert email_finder.classify_audience("careers@co.com") == "recruiter"
    assert email_finder.classify_audience("recruitment@co.com") == "recruiter"
    assert email_finder.classify_audience("founder@co.com") == "decision_maker"
    assert email_finder.classify_audience("nihal.upadhyay@co.com") == "decision_maker"
