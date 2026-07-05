"""Tests for job scoring and filtering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from job_radar.scorer import (
    build_daily_queue,
    description_rejected,
    filter_and_rank,
    location_tier,
    normalize_key,
    score_job,
    title_excluded,
)


def test_normalize_key_dedupes_formatting():
    a = normalize_key("Razorpay", "Junior Python Dev", "Bangalore")
    b = normalize_key("razorpay", "junior-python-dev", "bangalore")
    assert a == b


def test_title_excludes_java_and_senior(sample_config):
    assert title_excluded("Senior Python Developer", sample_config["title_exclude"])
    assert title_excluded("Java Backend Engineer", sample_config["title_exclude"])


def test_python_job_scores_high(sample_config, sample_python_job):
    score = score_job(sample_python_job, sample_config)
    assert score >= sample_config["min_score"]


def test_sql_dba_job_scores_high(sample_config, sample_sql_job):
    score = score_job(sample_sql_job, sample_config)
    assert score >= sample_config["min_score"]


def test_stale_job_scores_zero(sample_config, sample_python_job):
    old = datetime.now(timezone.utc) - timedelta(days=30)
    sample_python_job["posted_at"] = old.strftime("%Y-%m-%d")
    assert score_job(sample_python_job, sample_config) == 0.0


def test_filter_and_rank_sorts_by_score(sample_config, sample_python_job, sample_sql_job):
    ranked = filter_and_rank([sample_sql_job, sample_python_job], sample_config)
    assert len(ranked) == 2
    assert ranked[0]["score"] >= ranked[1]["score"]
    assert "dedupe_key" in ranked[0]


def test_junior_title_senior_jd_rejected(sample_config):
    job = {
        "company": "BadCo",
        "title": "Junior Python Developer",
        "location": "Hyderabad",
        "track": "python",
        "source": "linkedin",
        "job_url": "https://example.com/x",
        "description": "Minimum 5 years of experience leading a team of engineers.",
        "posted_at": "2026-07-01",
    }
    assert score_job(job, sample_config) == 0.0
    assert job.get("reject_reason") == "requires 5+ years"


def test_python_ai_role_rejected(sample_config):
    job = {
        "company": "AICo",
        "title": "Python AI Developer",
        "location": "Hyderabad",
        "track": "python",
        "source": "linkedin",
        "job_url": "https://example.com/ai",
        "description": "Build LLM pipelines with LangChain and PyTorch.",
        "posted_at": "2026-07-01",
    }
    assert score_job(job, sample_config) == 0.0
    assert job.get("reject_reason") == "ai/ml role"


def test_hyderabad_scores_above_remote(sample_config, sample_python_job):
    hyd = dict(sample_python_job)
    hyd["location"] = "Hyderabad, Telangana, India"
    remote = dict(sample_python_job)
    remote["location"] = "Remote, India"
    assert score_job(hyd, sample_config) > score_job(remote, sample_config)


def test_ambiguous_title_saved_by_database_jd(sample_config):
    job = {
        "company": "DataCo",
        "title": "Software Engineer",
        "location": "Hyderabad",
        "track": "python",
        "source": "greenhouse",
        "job_url": "https://example.com/se",
        "description": "PostgreSQL stored procedures, ETL migration, Aurora RDS, junior welcome.",
        "posted_at": "2026-07-01",
    }
    assert description_rejected(job["title"], job["description"], sample_config) is None
    assert score_job(job, sample_config) >= sample_config["min_score"]
    assert job["track"] == "sql_dba"


def test_build_daily_queue_dba_first(sample_config):
    jobs = [
        {"track": "python", "score": 99, "location_tier": 0},
        {"track": "python", "score": 95, "location_tier": 0},
        {"track": "sql_dba", "score": 80, "location_tier": 1},
        {"track": "sql_dba", "score": 78, "location_tier": 0},
    ]
    queue = build_daily_queue(jobs, sample_config)
    dba_count = sum(1 for j in queue if j["track"] == "sql_dba")
    assert dba_count >= 2


def test_location_tier_hyderabad(sample_config):
    assert location_tier("Hyderabad, India", sample_config) == 0
    assert location_tier("Bangalore, Karnataka", sample_config) == 1
