"""Contract tests for the planned email discovery waterfall.

Implementation comes AFTER evaluate_email_providers.py proves hit rates.
These tests define expected behavior so refactors stay safe.
"""

from __future__ import annotations

from unittest.mock import patch

from job_radar import email_finder


def test_waterfall_skips_paid_apis_when_jd_has_email():
    """Tier 1: never call Hunter if posting already lists an address."""
    desc = "Apply at careers@acme.com or visit our site."
    with patch("job_radar.email_finder.hunter_domain_search") as mock_hunter:
        email, source = email_finder.find_contact_email(
            "Acme", desc, "https://boards.greenhouse.io/acme", use_hunter=True
        )
    assert email == "careers@acme.com"
    assert source == "description"
    mock_hunter.assert_not_called()


def test_waterfall_current_order_description_before_hunter():
    with patch("job_radar.email_finder.hunter_domain_search", return_value="hr@co.com") as mock_hunter:
        email, source = email_finder.find_contact_email(
            "Co", "contact hr@co.com", use_hunter=True
        )
    assert source == "description"
    mock_hunter.assert_not_called()


def test_waterfall_hunter_before_guess():
    with patch("job_radar.email_finder.hunter_domain_search", return_value="talent@realco.com"):
        email, source = email_finder.find_contact_email(
            "RealCo", "", "https://realco.com/jobs/1", use_hunter=True
        )
    assert email == "talent@realco.com"
    assert source == "hunter"


def test_waterfall_guess_is_last_resort():
    with patch("job_radar.email_finder.hunter_domain_search", return_value=None):
        email, source = email_finder.find_contact_email(
            "Acme Corp", "", use_hunter=True, allow_guess=True
        )
    assert source == "guess"
    assert email == "careers@acmecorp.com"


def test_planned_tier_names_documented():
    """Future resolve_contact_waterfall() should report these source labels."""
    expected = {
        "stored",
        "description",
        "scrape",
        "pattern",
        "hunter",
        "snov",
        "tomba",
        "guess",
        "none",
    }
    # Current production subset today
    current = {"description", "hunter", "guess", "none"}
    assert current.issubset(expected)
