"""Tests for the outreach engine."""

from __future__ import annotations

from job_radar import outreach_engine, templates
from job_radar.email_finder import classify_audience

_SEED_CFG = {"outreach": {"seed": 42, "personalization_level": 1}}


def test_classify_audience():
    assert classify_audience("careers@razorpay.com") == "recruiter"
    assert classify_audience("founder@startup.io") == "decision_maker"


def test_jd_hook_extracts_keyword(sample_python_job):
    hook = templates.jd_hook(sample_python_job["description"], "python")
    assert "fastapi" in hook.lower() or "python" in hook.lower()


def test_python_initial_simple_structure(sample_python_job):
    job = {
        **sample_python_job,
        "contact_email": "cto@startup.io",
        "outreach_audience": "decision_maker",
    }
    profile = {
        "YOUR_NAME": "Test User",
        "YOUR_EMAIL": "test@example.com",
    }
    _, body = templates.initial_email(job, profile, _SEED_CFG)
    lower = body.lower()
    assert "dear hiring team" in lower
    assert "expiry tracker" in lower
    assert "expiry_tracker_final" in lower
    assert "youtube.com" in lower
    assert "resume is attached" in lower
    assert "test@example.com" in body
    assert templates.should_attach_resume(job, _SEED_CFG)


def test_dba_initial_includes_resume_and_email(sample_sql_job):
    job = {
        **sample_sql_job,
        "contact_email": "founder@startup.io",
        "outreach_audience": "decision_maker",
    }
    _, body = templates.initial_email(
        job, {"YOUR_NAME": "T", "YOUR_EMAIL": "dba@example.com"}, _SEED_CFG
    )
    lower = body.lower()
    assert "resume is attached" in lower
    assert "dba@example.com" in body
    assert "expiry_tracker_final" not in body


def test_dba_initial_uses_tr_story(sample_sql_job):
    job = {
        **sample_sql_job,
        "contact_email": "founder@startup.io",
        "outreach_audience": "decision_maker",
    }
    _, body = templates.initial_email(job, {"YOUR_NAME": "T"}, _SEED_CFG)
    lower = body.lower()
    assert "thomson reuters" in lower or "tr " in lower
    assert "aurora" in lower or "postgresql" in lower
    assert "5,000" in body or "5000" in body
    assert "informatica" in lower
    assert "that is direct experience" not in lower


def test_recruiter_initial_same_template_with_resume(sample_sql_job, sample_config):
    job = {
        **sample_sql_job,
        "contact_email": "careers@bankco.com",
        "outreach_audience": "recruiter",
    }
    cfg = {**sample_config, "outreach": {**sample_config.get("outreach", {}), "seed": 42}}
    _, body = templates.initial_email(job, {"YOUR_NAME": "D"}, cfg)
    assert "resume is attached" in body.lower() or "resume attached" in body.lower()
    assert templates.should_attach_resume(job, sample_config)


def test_personalization_level_affects_confidence(sample_python_job):
    job = {
        **sample_python_job,
        "contact_email": "founder@x.io",
        "outreach_audience": "decision_maker",
    }
    c0 = templates.compose_with_meta(
        job, {"YOUR_NAME": "T"}, {"outreach": {"seed": 1, "personalization_level": 0}}
    )
    c2 = templates.compose_with_meta(
        job,
        {"YOUR_NAME": "T"},
        {"outreach": {"seed": 1, "personalization_level": 2}},
    )
    assert c2.confidence.score >= c0.confidence.score


def test_followup_one_python_tone(sample_python_job):
    job = {
        **sample_python_job,
        "contact_email": "founder@startup.io",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    _, body = templates.followup_email(
        job, {"YOUR_NAME": "T", "YOUR_EMAIL": "py@example.com"}, 1, _SEED_CFG
    )
    lower = body.lower()
    assert "hope you're doing well" in lower
    assert "expiry tracker" in lower
    assert "expiry_tracker_final" in lower
    assert "resume is attached" in lower
    assert "py@example.com" in body


def test_followup_three_closes_gracefully(sample_python_job):
    _, body = templates.followup_email(sample_python_job, {"YOUR_NAME": "T"}, 3, _SEED_CFG)
    assert "final follow-up" in body.lower()
    assert "thank you for considering" in body.lower()


def test_followup_dba_uses_tr_experience(sample_sql_job):
    job = {
        **sample_sql_job,
        "contact_email": "founder@startup.io",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    _, body = templates.followup_email(job, {"YOUR_NAME": "T"}, 1, _SEED_CFG)
    lower = body.lower()
    assert "thomson reuters" in lower
    assert "postgresql" in lower


def test_extract_signals_returns_level(sample_python_job):
    signals = outreach_engine.extract_signals(sample_python_job, _SEED_CFG)
    assert signals.level == 1
    assert signals.stack_label
    assert signals.jd_themes


def test_confidence_score_present(sample_python_job):
    job = {
        **sample_python_job,
        "contact_email": "founder@startup.io",
        "outreach_audience": "decision_maker",
    }
    composed = templates.compose_with_meta(job, {"YOUR_NAME": "T"}, _SEED_CFG)
    assert 25 <= composed.confidence.score <= 95
    assert composed.confidence.signals_used
    assert composed.confidence.signals_missing


def test_same_body_for_recruiter_and_decision_maker(sample_python_job, sample_config):
    base = {
        **sample_python_job,
        "contact_email": "founder@startup.io",
        "outreach_audience": "decision_maker",
    }
    recruiter = {**base, "contact_email": "careers@testco.com", "outreach_audience": "recruiter"}
    cfg = {**sample_config, "outreach": {**sample_config.get("outreach", {}), "seed": 1}}
    dm_body = templates.initial_email(base, {"YOUR_NAME": "T"}, cfg)[1]
    rec_body = templates.initial_email(recruiter, {"YOUR_NAME": "T"}, cfg)[1]
    assert dm_body.split("\n\n")[1] == rec_body.split("\n\n")[1]
    assert dm_body.split("\n\n")[2] == rec_body.split("\n\n")[2]


def test_company_archetype_detection():
    assert outreach_engine.detect_company_archetype({"company": "Infosys", "description": ""}) == "enterprise"
    assert outreach_engine.detect_company_archetype({"company": "Stealth AI", "description": "YC startup"}) == "startup_small"
    assert outreach_engine.detect_company_archetype({"company": "Acme", "description": "Series A fintech"}) == "series_a"
