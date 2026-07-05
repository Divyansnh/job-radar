"""Tests for email templates and sending."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_radar import emailer, email_finder, templates


def test_initial_email_python_structure(sample_python_job, sample_config):
    job = {
        **sample_python_job,
        "contact_email": "hiring@testco.com",
        "outreach_audience": "recruiter",
    }
    profile = {
        "YOUR_NAME": "Test User",
        "LOOM_URL": "https://loom.com/test",
        "GITHUB_URL": "https://github.com/test",
    }
    cfg = {**sample_config, "outreach": {**sample_config.get("outreach", {}), "seed": 42}}
    subject, body = templates.initial_email(job, profile, cfg)
    assert "TestCo" in subject or "TestCo" in body
    assert "expiry tracker" in body.lower()
    assert "expiry_tracker_final" in body
    assert "youtube.com" in body
    assert "resume is attached" in body.lower()
    assert "Test User" in body


def test_followup_sequence(sample_python_job):
    job = {
        **sample_python_job,
        "contact_email": "founder@startup.io",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    profile = {
        "YOUR_NAME": "Test User",
        "GITHUB_URL": "https://github.com/test",
        "LOOM_URL": "https://loom.com/test",
    }
    _, body1 = templates.followup_email(job, profile, 1, {"outreach": {"seed": 42}})
    _, body3 = templates.followup_email(job, profile, 3, {"outreach": {"seed": 42}})
    assert "hope you're doing well" in body1.lower()
    assert "final follow-up" in body3.lower()


def test_guess_email_from_description():
    desc = "Contact recruiter at hiring@testcompany.com for details"
    email, source = email_finder.find_contact_email("TestCompany", desc, use_hunter=False)
    assert email == "hiring@testcompany.com"
    assert source == "description"


@patch("job_radar.emailer.smtplib.SMTP")
def test_send_followup_mocked(mock_smtp, sample_python_job, monkeypatch):
    monkeypatch.setenv("SMTP_USER", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "fake-password")
    monkeypatch.setenv("YOUR_NAME", "Test User")
    monkeypatch.setenv("LOOM_URL", "https://loom.com/test")

    job = {
        **sample_python_job,
        "id": 1,
        "contact_email": "recruiter@example.com",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    ok, meta = emailer.send_followup(job, 1)
    assert ok is True
    server.send_message.assert_called_once()
    sent = server.send_message.call_args[0][0]
    assert sent["To"] == "recruiter@example.com"


@patch("job_radar.emailer.smtplib.SMTP")
def test_send_email_mocked(mock_smtp, sample_config, sample_python_job, monkeypatch):
    monkeypatch.setenv("SMTP_USER", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "fake-password")
    monkeypatch.setenv("YOUR_NAME", "Test User")

    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    job = {
        **sample_python_job,
        "contact_email": "careers@testco.com",
        "contact_source": "description",
    }
    ok, meta = emailer.send_initial_outreach(job, sample_config)
    assert ok is True
    assert meta is not None
    server.send_message.assert_called_once()


def test_send_skipped_without_smtp(sample_python_job, sample_config, monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    ok, _meta = emailer.send_initial_outreach(sample_python_job, sample_config)
    assert ok is False
