"""Tests for activity analytics."""

from __future__ import annotations

from datetime import date, datetime, timezone

from job_radar import database
from job_radar.analytics import build_activity_report
from job_radar.scorer import normalize_key


def _job(company: str, title: str, track: str = "python") -> dict:
    return {
        "dedupe_key": normalize_key(company, title, "Hyderabad"),
        "company": company,
        "title": title,
        "location": "Hyderabad",
        "track": track,
        "source": "linkedin",
        "job_url": f"https://example.com/{company}",
        "description": "test",
        "score": 80.0,
        "posted_at": "2026-07-01",
    }


def test_applications_per_day_series(test_db):
    job_id = database.insert_job(_job("DayCo", "Dev"))
    database.mark_applied(job_id)
    series = database.applications_per_day(7)
    assert len(series) == 7
    assert sum(row["count"] for row in series) >= 1


def test_pipeline_funnel(test_db):
    database.insert_job(_job("Q", "Queued"))
    applied_id = database.insert_job(_job("A", "Applied"))
    database.mark_applied(applied_id)
    funnel = database.pipeline_funnel()
    assert funnel["tracked"] == 2
    assert funnel["queued"] == 1
    assert funnel["applied"] == 1


def test_build_activity_report_targets(sample_config, test_db):
    database.insert_job(_job("R1", "Role"))
    report = build_activity_report(sample_config)
    assert report["targets"]["applications_per_day"] == sample_config["daily_job_limit"]
    assert "activity_rates" in report
    assert len(report["chart_days"]) == 14
    assert any(r["id"] == "daily_apply" for r in report["activity_rates"])


def test_count_applied_on_date(test_db):
    job_id = database.insert_job(_job("TodayCo", "Dev"))
    database.mark_applied(job_id)
    assert database.count_applied_on_date(date.today()) == 1
