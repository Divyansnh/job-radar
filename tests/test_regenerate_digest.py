"""Tests for digest regeneration from tracker DB."""

from __future__ import annotations

from unittest.mock import patch

from job_radar import database
from job_radar.scorer import normalize_key


def _queued_job(company: str, title: str, track: str, score: float) -> dict:
    return {
        "dedupe_key": normalize_key(company, title, "Hyderabad"),
        "company": company,
        "title": title,
        "location": "Hyderabad, India",
        "track": track,
        "source": "linkedin",
        "job_url": f"https://example.com/{company.lower()}",
        "description": "postgresql sql python",
        "score": score,
        "posted_at": "2026-07-01",
    }


def test_regenerate_digest_writes_queue(test_db, tmp_path, sample_config):
    from job_radar import regenerate_digest

    database.insert_job(_queued_job("DbaCo", "Junior SQL DBA", "sql_dba", 110.0))
    database.insert_job(_queued_job("PyCo", "Junior Python Developer", "python", 90.0))

    with (
        patch("job_radar.regenerate_digest.ROOT", tmp_path),
        patch("job_radar.regenerate_digest.load_config", return_value=sample_config),
    ):
        regenerate_digest.main()

    out = tmp_path / "output" / "digest.html"
    html = out.read_text(encoding="utf-8")
    assert out.exists()
    assert "DbaCo" in html
    assert "PyCo" in html
    assert "Today's queue:" in html


def test_regenerate_digest_respects_daily_limit(test_db, tmp_path, sample_config):
    from job_radar import regenerate_digest

    for i in range(15):
        database.insert_job(
            _queued_job(f"Co{i}", f"Junior SQL DBA {i}", "sql_dba", 100.0 - i)
        )

    with (
        patch("job_radar.regenerate_digest.ROOT", tmp_path),
        patch("job_radar.regenerate_digest.load_config", return_value=sample_config),
    ):
        regenerate_digest.main()

    html = (tmp_path / "output" / "digest.html").read_text(encoding="utf-8")
    limit = sample_config.get("daily_job_limit", 10)
    assert f"<strong>Today's queue:</strong> {limit} jobs" in html
