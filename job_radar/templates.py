"""Email outreach — thin facade over the outreach engine."""

from __future__ import annotations

from job_radar.outreach_engine import (
    compose_with_meta,
    followup_email,
    initial_email,
    jd_hook,
    should_attach_resume,
)

__all__ = [
    "compose_with_meta",
    "followup_email",
    "initial_email",
    "jd_hook",
    "should_attach_resume",
]
