"""Tests for healthcheck module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from job_radar import healthcheck


def test_check_python_version():
    assert healthcheck.check_python_version() is True


def test_check_project_files(project_root: Path):
    assert healthcheck.check_project_files() is True


def test_check_scorer_and_digest():
    assert healthcheck.check_scorer_and_digest() is True


def test_check_database_roundtrip():
    assert healthcheck.check_database_roundtrip() is True


def test_main_returns_zero_when_checks_pass():
    with (
        patch.object(healthcheck, "check_dependencies", return_value=True),
        patch.object(healthcheck, "check_env_configured", return_value=True),
        patch.object(healthcheck, "check_resumes", return_value=True),
        patch("sys.argv", ["healthcheck"]),
    ):
        assert healthcheck.main() == 0


def test_main_includes_live_checks_with_flag():
    with (
        patch.object(healthcheck, "check_dependencies", return_value=True),
        patch.object(healthcheck, "check_env_configured", return_value=True),
        patch.object(healthcheck, "check_resumes", return_value=True),
        patch.object(healthcheck, "check_live_ats", return_value=True) as live_ats,
        patch.object(healthcheck, "check_live_portal", return_value=True) as live_portal,
        patch("sys.argv", ["healthcheck", "--live"]),
    ):
        assert healthcheck.main() == 0
        live_ats.assert_called_once()
        live_portal.assert_called_once()
