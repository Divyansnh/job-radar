"""Tests for CLI helper scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_send_one_job_dry_run_missing_id():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "send_one_job.py"), "999999", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
    )
    assert result.returncode == 1
    assert "ERROR" in result.stdout or "ERROR" in result.stderr


def test_send_one_job_dry_run_in_process(test_db, sample_python_job, monkeypatch):
    import importlib.util

    from job_radar import database

    job = {
        "dedupe_key": "script-test-key",
        "company": sample_python_job["company"],
        "title": sample_python_job["title"],
        "location": sample_python_job["location"],
        "track": sample_python_job["track"],
        "source": sample_python_job["source"],
        "job_url": sample_python_job["job_url"],
        "description": "Contact hiring@scripttest.com for details",
        "score": 90.0,
        "posted_at": sample_python_job["posted_at"],
    }
    job_id = database.insert_job(job)
    assert job_id is not None

    spec = importlib.util.spec_from_file_location(
        "send_one_job", ROOT / "scripts" / "send_one_job.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    monkeypatch.setattr(sys, "argv", ["send_one_job.py", str(job_id), "--dry-run"])
    assert mod.main() == 0


@pytest.mark.integration
def test_live_smtp_login():
    """Optional: verify Gmail SMTP credentials in .env (no email sent)."""
    import os
    import smtplib

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    user = os.getenv("SMTP_USER")
    pw = os.getenv("SMTP_PASSWORD")
    if not user or not pw:
        pytest.skip("SMTP not configured")

    with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587)), timeout=15) as s:
        s.starttls()
        s.login(user, pw)
