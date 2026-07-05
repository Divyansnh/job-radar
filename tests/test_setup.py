"""Verify project files and configuration structure."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_project_structure_exists(project_root: Path):
    required = [
        "config.yaml",
        "companies.yaml",
        ".env",
        "requirements.txt",
        "job_radar/daily.py",
        "job_radar/ats_fetcher.py",
        "job_radar/portal_scraper.py",
        "job_radar/scorer.py",
        "job_radar/database.py",
        "job_radar/emailer.py",
        "job_radar/digest.py",
        "job_radar/templates.py",
        "assets",
        "scripts/setup.bat",
    ]
    missing = [p for p in required if not (project_root / p).exists()]
    assert not missing, f"Missing: {missing}"


def test_config_yaml_valid(sample_config: dict):
    assert sample_config["daily_job_limit"] == 10
    assert sample_config["max_age_days"] == 14
    assert "python" in sample_config["search_terms"]
    assert "sql_dba" in sample_config["search_terms"]
    assert "linkedin" in sample_config["portals"]
    assert "indeed" in sample_config.get("optional_portals", [])
    assert sample_config["location_priority"]["primary"] == "Hyderabad"
    assert sample_config["track_priority"][0] == "sql_dba"


def test_companies_yaml_valid(project_root: Path):
    with open(project_root / "companies.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    companies = data.get("companies", [])
    assert len(companies) >= 10, "Expected at least 10 companies in watchlist"
    for c in companies:
        assert c.get("name")
        assert c.get("ats") in ("greenhouse", "lever", "ashby")
        assert c.get("token")
        assert c.get("track") in ("python", "sql_dba", "both")


def test_env_file_has_required_keys(project_root: Path):
    env_path = project_root / ".env"
    text = env_path.read_text(encoding="utf-8")
    for key in ("SMTP_USER", "SMTP_PASSWORD", "YOUR_NAME", "GITHUB_URL", "LOOM_URL"):
        assert key in text


def test_resume_paths_configured(sample_config: dict, project_root: Path):
    for track, rel in sample_config["resume_paths"].items():
        path = project_root / rel
        # Paths must be configured; files added by user before go-live
        assert track in ("python", "sql_dba")
        assert path.parent.name == "assets"
