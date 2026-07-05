"""End-to-end dry run: full pipeline with network calls mocked."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from job_radar import database


@pytest.fixture
def isolated_run(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "e2e.db")
    return tmp_path


def test_e2e_dry_run_pipeline(isolated_run, sample_config, sample_python_job, sample_sql_job):
    mock_company_jobs = [sample_python_job]
    mock_portal_jobs = [sample_sql_job]
    digest_path = isolated_run / "output" / "digest.html"

    with (
        patch("job_radar.daily.load_config", return_value=sample_config),
        patch("job_radar.daily.load_companies", return_value=[]),
        patch("job_radar.daily.ROOT", isolated_run),
        patch("job_radar.ats_fetcher.fetch_all_companies", return_value=mock_company_jobs),
        patch("job_radar.portal_scraper.scrape_portals", return_value=mock_portal_jobs),
        patch("job_radar.emailer.send_initial_outreach", return_value=(False, None)),
        patch("job_radar.emailer.send_followup", return_value=(False, None)),
    ):
        from job_radar.daily import run

        database.init_db()
        run()

    assert database.stats()["total"] >= 2
    queue = database.get_todays_queue(10)
    assert len(queue) >= 2
    assert digest_path.exists()
    assert "TestCo" in digest_path.read_text(encoding="utf-8")


def test_e2e_writes_digest_under_isolated_root(
    isolated_run, sample_config, sample_python_job, sample_sql_job
):
    """Regression: dry-run must not write to the real output/digest.html."""
    from job_radar import digest

    mock_company_jobs = [sample_python_job]
    mock_portal_jobs = [sample_sql_job]

    with (
        patch("job_radar.daily.load_config", return_value=sample_config),
        patch("job_radar.daily.load_companies", return_value=[]),
        patch("job_radar.daily.ROOT", isolated_run),
        patch("job_radar.ats_fetcher.fetch_all_companies", return_value=mock_company_jobs),
        patch("job_radar.portal_scraper.scrape_portals", return_value=mock_portal_jobs),
        patch("job_radar.emailer.send_initial_outreach", return_value=(False, None)),
        patch("job_radar.emailer.send_followup", return_value=(False, None)),
        patch.object(digest, "write_digest", wraps=digest.write_digest) as write_mock,
    ):
        from job_radar.daily import run

        database.init_db()
        run()

    write_mock.assert_called_once()
    out_path = write_mock.call_args[0][2]
    assert isolated_run in out_path.parents


def test_e2e_marks_email_sent_when_outreach_succeeds(
    isolated_run, sample_config, sample_python_job, sample_sql_job
):
    """When SMTP send succeeds, daily run should mark jobs as sent."""
    mock_company_jobs = [sample_python_job]
    mock_portal_jobs = [sample_sql_job]

    with (
        patch("job_radar.daily.load_config", return_value=sample_config),
        patch("job_radar.daily.load_companies", return_value=[]),
        patch("job_radar.daily.ROOT", isolated_run),
        patch("job_radar.ats_fetcher.fetch_all_companies", return_value=mock_company_jobs),
        patch("job_radar.portal_scraper.scrape_portals", return_value=mock_portal_jobs),
        patch("job_radar.emailer.send_initial_outreach", return_value=(True, '{"persona":"builder"}')),
        patch("job_radar.emailer.send_followup", return_value=(False, None)),
    ):
        from job_radar.daily import run

        database.init_db()
        run()

    with database._connect() as conn:
        sent = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE outreach_status = 'sent'"
        ).fetchone()[0]
    assert sent >= 1


@pytest.mark.integration
def test_live_greenhouse_fetch():
    """Optional live test: hits Razorpay public ATS API."""
    from job_radar.ats_fetcher import fetch_greenhouse

    jobs = fetch_greenhouse({"name": "Razorpay", "track": "python", "ats": "greenhouse", "token": "razorpay"})
    assert isinstance(jobs, list)


@pytest.mark.integration
def test_live_portal_scrape_sample(sample_config):
    """Optional live test: one Naukri search (slow, may rate-limit)."""
    pytest.importorskip("jobspy")
    from jobspy import scrape_jobs

    df = scrape_jobs(
        site_name=["naukri"],
        search_term="junior python developer",
        location="India",
        results_wanted=5,
        hours_old=336,
    )
    assert df is not None
