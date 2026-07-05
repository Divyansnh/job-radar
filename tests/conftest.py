"""Shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def sample_config() -> dict:
    path = ROOT / "config.yaml"
    if not path.exists():
        path = ROOT / "config.example.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    from job_radar import database

    db_file = tmp_path / "test_tracker.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.init_db()
    return db_file


@pytest.fixture
def sample_python_job() -> dict:
    return {
        "company": "TestCo",
        "title": "Junior Python Developer",
        "location": "Bangalore",
        "track": "python",
        "source": "greenhouse",
        "job_url": "https://example.com/jobs/1",
        "description": "Python FastAPI PostgreSQL REST API Git Docker AWS",
        "posted_at": "2026-07-01",
    }


@pytest.fixture
def sample_sql_job() -> dict:
    return {
        "company": "BankCo",
        "title": "Junior SQL DBA",
        "location": "Mumbai",
        "track": "sql_dba",
        "source": "naukri",
        "job_url": "https://example.com/jobs/2",
        "description": "SQL Server backup restore indexing replication T-SQL",
        "posted_at": "2026-07-02",
    }
