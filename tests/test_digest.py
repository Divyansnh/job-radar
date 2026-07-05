"""Tests for HTML digest generation."""

from __future__ import annotations

from job_radar.digest import render_digest, write_digest


def test_render_digest_contains_jobs(sample_python_job):
    html = render_digest([sample_python_job], {"total": 1, "applied": 0, "emailed": 0})
    assert "TestCo" in html
    assert "Junior Python Developer" in html
    assert "Apply" in html


def test_write_digest_creates_file(tmp_path, sample_python_job):
    out = tmp_path / "digest.html"
    write_digest([sample_python_job], {"total": 1, "applied": 0, "emailed": 0}, out)
    assert out.exists()
    assert "Job Radar" in out.read_text(encoding="utf-8")
