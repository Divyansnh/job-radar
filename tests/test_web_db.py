"""Tests for extended database queries."""

from __future__ import annotations

from job_radar import database
from job_radar.scorer import normalize_key


def _job(company: str, title: str, track: str = "python", score: float = 80.0) -> dict:
    return {
        "dedupe_key": normalize_key(company, title, "Hyderabad"),
        "company": company,
        "title": title,
        "location": "Hyderabad",
        "track": track,
        "source": "linkedin",
        "job_url": f"https://example.com/{company}",
        "description": "test",
        "score": score,
        "posted_at": "2026-07-01",
    }


def test_list_jobs_filter_by_track(test_db):
    database.insert_job(_job("A", "Role A", track="sql_dba"))
    database.insert_job(_job("B", "Role B", track="python"))
    dba = database.list_jobs(track="sql_dba")
    assert len(dba) == 1
    assert dba[0]["company"] == "A"


def test_list_jobs_search(test_db):
    database.insert_job(_job("Infosys", "Python Dev"))
    database.insert_job(_job("Amazon", "DBA Role", track="sql_dba"))
    hits = database.list_jobs(search="Infosys")
    assert len(hits) == 1
    assert hits[0]["company"] == "Infosys"


def test_get_job_and_notes(test_db):
    job_id = database.insert_job(_job("NoteCo", "Dev"))
    assert job_id is not None
    job = database.get_job(job_id)
    assert job is not None
    assert job["company"] == "NoteCo"
    assert database.update_notes(job_id, "Called recruiter")
    updated = database.get_job(job_id)
    assert updated["notes"] == "Called recruiter"


def test_list_applied_jobs(test_db):
    job_id = database.insert_job(_job("ApplyCo", "Dev"))
    database.mark_applied(job_id)
    applied = database.list_applied_jobs()
    assert len(applied) == 1
    assert applied[0]["status"] == "applied"
    assert applied[0]["applied_at"] is not None


def test_dashboard_stats(test_db):
    database.insert_job(_job("Q1", "Dev", score=90))
    database.insert_job(_job("Q2", "DBA", track="sql_dba", score=95))
    job_id = database.insert_job(_job("Q3", "Other"))
    database.mark_applied(job_id)
    stats = database.dashboard_stats()
    assert stats["total"] == 3
    assert stats["queued"] == 2
    assert stats["applied"] == 1
    assert stats["sql_dba"] == 1
    assert stats["python"] == 2


def test_count_jobs(test_db):
    database.insert_job(_job("C1", "A"))
    database.insert_job(_job("C2", "B", track="sql_dba"))
    assert database.count_jobs(track="sql_dba") == 1
    assert database.count_jobs() == 2
