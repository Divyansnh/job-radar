"""Tests for portal scraper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from job_radar import portal_scraper


def test_scrape_portals_without_jobspy(sample_config):
    with patch.dict("sys.modules", {"jobspy": None}):
        jobs = portal_scraper.scrape_portals(sample_config)
    assert jobs == []


@patch("job_radar.portal_scraper._scrape_one")
def test_scrape_portals_dedupes_urls(mock_scrape, sample_config):
    mock_scrape.return_value = [
        {
            "company": "Co",
            "title": "Dev",
            "location": "Hyd",
            "job_url": "https://example.com/a",
            "description": "python",
            "posted_at": "2026-07-01",
            "source": "linkedin",
        },
        {
            "company": "Co",
            "title": "Dev 2",
            "location": "Hyd",
            "job_url": "https://example.com/a",
            "description": "python",
            "posted_at": "2026-07-01",
            "source": "linkedin",
        },
    ]
    with patch.dict("sys.modules", {"jobspy": MagicMock()}):
        jobs = portal_scraper.scrape_portals(sample_config)
    assert len(jobs) == 1


@patch("jobspy.scrape_jobs")
def test_scrape_one_maps_dataframe(mock_scrape_jobs):
    mock_scrape_jobs.return_value = pd.DataFrame(
        [
            {
                "company": "TestCo",
                "title": "Junior Python",
                "location": "Hyderabad",
                "job_url": "https://jobs.example/1",
                "description": "FastAPI",
                "date_posted": "2026-07-01",
                "site": "naukri",
            }
        ]
    )
    jobs = portal_scraper._scrape_one("naukri", "python", "Hyderabad", 336, 5)
    assert len(jobs) == 1
    assert jobs[0]["company"] == "TestCo"
    assert jobs[0]["source"] == "naukri"
