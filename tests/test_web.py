"""Tests for Flask web dashboard."""

from __future__ import annotations

import pytest

from job_radar import database
from job_radar.scorer import normalize_key
from job_radar.web import create_app


@pytest.fixture
def app(test_db):
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _insert(company: str, title: str, track: str = "python", score: float = 80.0) -> int:
    job_id = database.insert_job(
        {
            "dedupe_key": normalize_key(company, title, "Hyderabad"),
            "company": company,
            "title": title,
            "location": "Hyderabad",
            "track": track,
            "source": "linkedin",
            "job_url": f"https://example.com/{company}",
            "description": "Python PostgreSQL role",
            "score": score,
            "posted_at": "2026-07-01",
        }
    )
    assert job_id is not None
    return job_id


def test_dashboard_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Activity Dashboard" in resp.data
    assert b"paceChart" in resp.data


def test_all_jobs_page(client, test_db):
    _insert("WebCo", "Junior Dev")
    resp = client.get("/jobs")
    assert resp.status_code == 200
    assert b"WebCo" in resp.data


def test_job_detail_and_mark_applied(client, test_db):
    job_id = _insert("ApplyWeb", "Engineer")
    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert b"ApplyWeb" in resp.data

    resp = client.post(f"/jobs/{job_id}/applied", follow_redirects=True)
    assert resp.status_code == 200
    assert database.get_job(job_id)["status"] == "applied"
    assert b"Applied" in resp.data or b"applied" in resp.data.lower()


def test_save_notes(client, test_db):
    job_id = _insert("NotesCo", "Dev")
    resp = client.post(
        f"/jobs/{job_id}/notes",
        data={"notes": "Great fit"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert database.get_job(job_id)["notes"] == "Great fit"


def test_jobs_page_has_metrics(client, test_db):
    _insert("MetricsCo", "DBA", track="sql_dba", score=99)
    resp = client.get("/jobs")
    assert resp.status_code == 200
    assert b"Today's digest" in resp.data
    assert b"Pending outreach" in resp.data
    assert b"MetricsCo" in resp.data


def test_digest_and_outreach_pages(client):
    resp = client.get("/outreach")
    assert resp.status_code == 200
    assert b"Due now" in resp.data
    assert b"tab-bar" in resp.data
    assert client.get("/outreach?view=sent").status_code == 200
    assert client.get("/digest").status_code == 200
    assert client.get("/applied").status_code == 200


def test_applied_page_has_metrics_and_filters(client, test_db):
    job_id = _insert("AppliedCo", "Engineer")
    database.mark_applied(job_id)
    resp = client.get("/applied")
    assert resp.status_code == 200
    assert b"Total applied" in resp.data
    assert b"AppliedCo" in resp.data
    assert client.get("/applied?track=python").status_code == 200


def test_queue_page_removed(client):
    assert client.get("/queue").status_code == 404


def test_job_not_found(client):
    assert client.get("/jobs/99999").status_code == 404
