"""Tests for browser scraper helpers."""

from __future__ import annotations

from job_radar.browser_scraper import _abs_url, _load_browser_portals


def test_abs_url_relative():
    assert _abs_url("/job/123", "https://www.hirist.com") == "https://www.hirist.com/job/123"


def test_abs_url_full():
    assert _abs_url("https://x.com/j", "https://www.hirist.com") == "https://x.com/j"


def test_browser_portals_config_loads(project_root):
    portals = _load_browser_portals(project_root)
    assert "naukri" in portals
    assert "hirist" in portals
    assert portals["naukri"].get("login_url")
