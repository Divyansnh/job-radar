"""Unit tests for ATS fetcher title filtering."""

from __future__ import annotations

from job_radar.ats_fetcher import fetch_company_jobs


def test_irrelevant_ats_returns_empty_for_bad_token():
    company = {"name": "Fake", "track": "python", "ats": "greenhouse", "token": "this-company-does-not-exist-xyz"}
    jobs = fetch_company_jobs(company)
    assert jobs == []


def test_title_filter_logic_via_mock(monkeypatch):
    company = {"name": "MockCo", "track": "python", "ats": "greenhouse", "token": "mock"}

    fake_jobs = {
        "jobs": [
            {
                "title": "Senior Java Architect",
                "location": {"name": "India"},
                "absolute_url": "https://example.com/1",
                "content": "",
                "updated_at": "2026-07-01",
            },
            {
                "title": "Junior Python Developer",
                "location": {"name": "Bangalore"},
                "absolute_url": "https://example.com/2",
                "content": "Python FastAPI",
                "updated_at": "2026-07-01",
            },
        ]
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return fake_jobs

    monkeypatch.setattr("job_radar.ats_fetcher.requests.get", lambda *a, **k: FakeResp())
    jobs = fetch_company_jobs(company)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Junior Python Developer"
