"""Safety tests before removing dead/redundant code.

These lock in behavior the live pipeline depends on. If a removal breaks any
of these, the dead code was still doing real work.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_radar import analytics, database, emailer, outreach_engine, templates

_SEED = {"outreach": {"seed": 42, "personalization_level": 1}}
_PROFILE = {
    "YOUR_NAME": "Test User",
    "YOUR_EMAIL": "test@example.com",
    "GITHUB_URL": "https://github.com/test",
}


def test_initial_emails_pass_copy_lint(sample_python_job, sample_sql_job):
    """Composed outreach must not contain banned spam phrases."""
    for job in (
        {**sample_python_job, "contact_email": "founder@x.io", "outreach_audience": "decision_maker"},
        {**sample_sql_job, "contact_email": "hr@bank.com", "outreach_audience": "recruiter"},
    ):
        composed = templates.compose_with_meta(job, _PROFILE, _SEED)
        outreach_engine._lint(composed.body)


def test_decision_maker_email_never_contains_connection_phrase(sample_python_job):
    """Emails must not rely on the unused connection block copy."""
    job = {
        **sample_python_job,
        "contact_email": "founder@startup.io",
        "outreach_audience": "decision_maker",
    }
    for seed in range(20):
        composed = templates.compose_with_meta(
            job, _PROFILE, {"outreach": {"seed": seed, "personalization_level": 1}}
        )
        assert "that overlap is what made me write" not in composed.body


def test_public_templates_api_covers_live_pipeline():
    """Only symbols imported by prod code need to stay on templates facade."""
    required = (
        "compose_with_meta",
        "initial_email",
        "followup_email",
        "jd_hook",
        "should_attach_resume",
    )
    for name in required:
        assert hasattr(templates, name), f"templates.{name} missing"


def test_compose_with_meta_returns_usable_email(sample_python_job):
    composed = templates.compose_with_meta(
        {
            **sample_python_job,
            "contact_email": "founder@x.io",
            "outreach_audience": "decision_maker",
        },
        _PROFILE,
        _SEED,
    )
    assert composed.subject
    assert composed.body
    assert composed.confidence.score >= 25
    meta = composed.meta_json()
    assert "persona" in meta
    assert "confidence_score" in meta


def test_initial_and_followup_tuple_helpers_match_compose(sample_python_job):
    job = {
        **sample_python_job,
        "contact_email": "founder@startup.io",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    subj_a, body_a = templates.initial_email(job, _PROFILE, _SEED)
    composed = templates.compose_with_meta(job, _PROFILE, _SEED)
    assert subj_a == composed.subject
    assert body_a == composed.body

    subj_f, body_f = templates.followup_email(job, _PROFILE, 1, _SEED)
    fu = outreach_engine.compose_followup(job, _PROFILE, 1, _SEED)
    assert subj_f == fu.subject
    assert body_f == fu.body


def test_emailer_does_not_require_your_email_env(sample_python_job, sample_config, monkeypatch):
    """SMTP uses SMTP_USER, not YOUR_EMAIL — YOUR_EMAIL in profile is redundant."""
    monkeypatch.setenv("SMTP_USER", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "fake")
    monkeypatch.setenv("YOUR_NAME", "Test User")
    monkeypatch.delenv("YOUR_EMAIL", raising=False)

    job = {**sample_python_job, "contact_email": "careers@testco.com", "id": 1}
    with patch("job_radar.emailer.smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value = MagicMock()
        ok, meta = emailer.send_initial_outreach(job, sample_config)
    assert ok is True
    assert meta is not None


def test_analytics_report_without_unused_target_keys(sample_config):
    """Dashboard works even if outreach_rate_pct / followup_completion_pct are absent."""
    cfg = dict(sample_config)
    activity = dict(cfg.get("activity_targets") or {})
    activity.pop("outreach_rate_pct", None)
    activity.pop("followup_completion_pct", None)
    cfg["activity_targets"] = activity

    report = analytics.build_activity_report(cfg)
    assert "activity_rates" in report
    assert "outreach" in {r["id"] for r in report["activity_rates"]}
    assert "followup" in {r["id"] for r in report["activity_rates"]}
    assert report["targets"]["applications_per_day"] > 0


def test_outreach_meta_persisted_on_send(test_db, sample_config):
    job_id = database.insert_job(
        {
            "dedupe_key": "safety-test-key",
            "company": "SafeCo",
            "title": "Python Dev",
            "location": "India",
            "track": "python",
            "source": "test",
            "job_url": "https://example.com/safe",
            "description": "python fastapi",
            "score": 80.0,
        }
    )
    meta = '{"persona":"curious","confidence_score":85}'
    database.mark_email_sent(job_id, [3, 7, 12], meta)
    job = database.get_job(job_id)
    assert job["outreach_meta"] is not None
    assert "curious" in job["outreach_meta"]
