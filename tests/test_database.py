"""Tests for SQLite tracker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from job_radar import database
from job_radar.scorer import normalize_key


def _job(company="Acme", title="Junior Python Developer", track="python"):
    return {
        "dedupe_key": normalize_key(company, title, "India"),
        "company": company,
        "title": title,
        "location": "India",
        "track": track,
        "source": "greenhouse",
        "job_url": "https://example.com/job",
        "description": "python fastapi",
        "score": 80.0,
        "posted_at": "2026-07-01",
    }


def test_init_and_insert(test_db, sample_python_job):
    job = _job()
    job["dedupe_key"] = normalize_key("TestCo", "Junior Python Developer", "Bangalore")
    job_id = database.insert_job(job)
    assert job_id is not None
    assert database.job_exists(job["dedupe_key"])


def test_insert_dedupes(test_db):
    job = _job()
    assert database.insert_job(job) is not None
    assert database.insert_job(job) is None


def test_queue_orders_by_score(test_db):
    low = _job("LowCo", "Junior Python Dev A")
    low["score"] = 60.0
    high = _job("HighCo", "Junior Python Dev B")
    high["score"] = 95.0
    database.insert_job(low)
    database.insert_job(high)
    queue = database.get_todays_queue(10)
    assert queue[0]["company"] == "HighCo"


def test_followup_schedule_from_initial_email(test_db):
    job = _job()
    job_id = database.insert_job(job)
    followup_days = [3, 7, 12]
    database.mark_email_sent(job_id, followup_days)

    with database._connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    assert row["outreach_status"] == "sent"
    assert row["next_followup_at"] is not None

    database.mark_followup_sent(job_id, 1, followup_days)
    with database._connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    initial = datetime.fromisoformat(row["initial_email_sent_at"])
    expected_next = initial + timedelta(days=7)
    actual_next = datetime.fromisoformat(row["next_followup_at"])
    assert actual_next.date() == expected_next.date()
    assert row["followup_count"] == 1


def test_get_due_followups_selects_overdue(test_db):
    job = _job()
    job_id = database.insert_job(job)
    database.mark_email_sent(job_id, [3, 7, 12])

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with database._connect() as conn:
        conn.execute(
            "UPDATE jobs SET next_followup_at = ? WHERE id = ?",
            (past, job_id),
        )

    due = database.get_due_followups()
    assert any(j["id"] == job_id for j in due)


def test_update_contact_email(test_db):
    job_id = database.insert_job(_job())
    assert database.update_contact_email(job_id, " hr@test.com ")
    job = database.get_job(job_id)
    assert job["contact_email"] == "hr@test.com"


def test_outreach_meta_and_reply_outcome(test_db):
    job_id = database.insert_job(_job())
    meta = '{"persona":"curious","structure":["observation","question","proof","cta"]}'
    database.mark_email_sent(job_id, [3, 7, 12], meta)
    database.set_reply_outcome(job_id, "replied")

    job = database.get_job(job_id)
    assert job["reply_outcome"] == "replied"
    assert job["outreach_meta"] is not None
    assert "curious" in job["outreach_meta"]

    stats = database.outreach_learning_stats()
    assert stats["total_sent"] >= 1
