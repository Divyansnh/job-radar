"""Tests for LinkedIn hints and manual contact workflow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_radar import database, email_finder
from job_radar.contact_import import parse_contact_lines
from job_radar.linkedin_hints import build_linkedin_hints


def test_guess_disabled_by_default():
    email, source = email_finder.find_contact_email("Acme Corp", use_hunter=False)
    assert email is None
    assert source == "none"


def test_guess_when_explicitly_allowed():
    email, source = email_finder.find_contact_email(
        "Acme Corp", use_hunter=False, allow_guess=True
    )
    assert email == "careers@acmecorp.com"
    assert source == "guess"


def test_is_trusted_source():
    assert email_finder.is_trusted_source("description")
    assert email_finder.is_trusted_source("hunter")
    assert email_finder.is_trusted_source("manual")
    assert not email_finder.is_trusted_source("guess")
    assert not email_finder.is_trusted_source("none")


def test_parse_contact_lines():
    text = """
    Priya Sharma | priya@acme.com | https://linkedin.com/in/priya
    recruiter@acme.com
    """
    rows = parse_contact_lines(text)
    assert len(rows) == 2
    assert rows[0]["email"] == "priya@acme.com"
    assert rows[0]["name"] == "Priya Sharma"
    assert rows[1]["email"] == "recruiter@acme.com"


def test_linkedin_hints_include_searches(sample_python_job):
    hints = build_linkedin_hints(sample_python_job)
    assert hints.company == "TestCo"
    assert len(hints.searches) >= 4
    assert all(s.url.startswith("https://www.linkedin.com/search") for s in hints.searches)


def test_add_job_contacts(test_db):
    job_id = database.insert_job(
        {
            "dedupe_key": "contact-test",
            "company": "Co",
            "title": "Dev",
            "location": "India",
            "track": "python",
            "source": "test",
            "job_url": "https://example.com/j",
            "description": "python",
            "score": 80.0,
        }
    )
    n = database.add_job_contacts(
        job_id,
        [{"name": "A", "email": "a@co.com", "linkedin_url": ""}],
    )
    assert n == 1
    contacts = database.list_job_contacts(job_id)
    assert contacts[0]["email"] == "a@co.com"


@patch("job_radar.emailer.send_email")
def test_send_initial_marks_needs_contacts(mock_send, sample_python_job, sample_config, test_db):
    from job_radar import emailer

    job_id = database.insert_job(
        {
            **sample_python_job,
            "dedupe_key": "needs-li",
            "description": "Python role with no email in text",
            "company": "NeedsLiCo",
            "title": "Python Dev",
            "location": "India",
            "track": "python",
            "source": "test",
            "job_url": "https://example.com/j",
            "score": 80.0,
        }
    )
    job = database.get_job(job_id)
    ok, meta = emailer.send_initial_outreach(job, sample_config)
    assert ok is False
    assert meta is None
    mock_send.assert_not_called()
    updated = database.get_job(job_id)
    assert updated["outreach_status"] == "needs_contacts"


@patch("job_radar.emailer.send_email", return_value=True)
def test_send_to_manual_contact(mock_send, sample_python_job, sample_config, test_db):
    from job_radar import emailer

    job_id = database.insert_job(
        {
            "dedupe_key": "manual-send",
            "company": "Acuity",
            "title": "Python Dev",
            "location": "India",
            "track": "python",
            "source": "test",
            "job_url": "https://example.com/j",
            "description": "no email",
            "score": 80.0,
        }
    )
    database.add_job_contacts(
        job_id, [{"name": "Nihal", "email": "nihal@acuity.com", "linkedin_url": ""}]
    )
    contact = database.list_job_contacts(job_id)[0]
    job = database.get_job(job_id)
    ok, meta = emailer.send_to_manual_contact(job, contact, sample_config)
    assert ok is True
    assert meta is not None
    mock_send.assert_called_once()
    updated = database.get_job(job_id)
    assert updated["outreach_status"] == "sent"
