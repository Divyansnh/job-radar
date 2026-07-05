"""Send outreach and follow-up emails via Gmail SMTP."""

from __future__ import annotations

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from job_radar import email_finder, templates
from job_radar.outreach_engine import compose_followup, compose_with_meta


def _profile() -> dict[str, str]:
    return {
        "YOUR_NAME": os.getenv("YOUR_NAME", ""),
        "YOUR_EMAIL": os.getenv("YOUR_EMAIL", "") or os.getenv("SMTP_USER", ""),
        "GITHUB_URL": os.getenv("GITHUB_URL", ""),
        "PROJECT_GITHUB_URL": os.getenv("PROJECT_GITHUB_URL", ""),
        "LOOM_URL": os.getenv("LOOM_URL", ""),
        "DEMO_VIDEO_URL": os.getenv("DEMO_VIDEO_URL", ""),
        "LINKEDIN_URL": os.getenv("LINKEDIN_URL", ""),
    }


def _smtp_configured() -> bool:
    return bool(
        os.getenv("SMTP_USER")
        and os.getenv("SMTP_PASSWORD")
        and os.getenv("YOUR_NAME")
    )


def resolve_contact_email(
    job: dict[str, Any], config: dict | None = None
) -> tuple[str | None, str]:
    if job.get("contact_email"):
        source = job.get("contact_source") or "stored"
        return job["contact_email"], source

    cfg = (config or {}).get("outreach", {})
    allow_guess = bool(cfg.get("allow_guess", False))
    return email_finder.find_contact_email(
        job.get("company", ""),
        job.get("description", "") or "",
        job.get("job_url"),
        allow_guess=allow_guess,
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    resume_path: Path | None = None,
) -> bool:
    if not _smtp_configured():
        print(f"  [skip email] SMTP not configured — would send to {to}")
        return False

    msg = MIMEMultipart()
    msg["From"] = os.getenv("SMTP_USER", "")
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if resume_path and resume_path.exists():
        with open(resume_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=resume_path.name)
        part["Content-Disposition"] = f'attachment; filename="{resume_path.name}"'
        msg.attach(part)

    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
            server.send_message(msg)
        return True
    except smtplib.SMTPException as exc:
        print(f"  [email error] {exc}")
        return False


def send_initial_outreach(job: dict[str, Any], config: dict) -> tuple[bool, str | None]:
    from job_radar import database

    to, source = resolve_contact_email(job, config)
    if not to or not email_finder.is_trusted_source(source):
        reason = source if not to else f"untrusted:{source}"
        print(
            f"  [needs contacts] {job.get('company')} — "
            f"no verified email ({reason}). Use LinkedIn hints on the job page."
        )
        job_id = job.get("id")
        if job_id:
            database.set_outreach_status(job_id, "needs_contacts")
        return False, None

    if not job.get("contact_email"):
        job["contact_email"] = to
        job_id = job.get("id")
        if job_id:
            database.update_contact_email(job_id, to, source=source)
        print(f"  [email found via {source}] {to}")

    from job_radar.email_finder import classify_audience

    audience = classify_audience(to)
    job["outreach_audience"] = audience
    print(f"  [outreach] {audience} → {to}")

    profile = _profile()
    composed = compose_with_meta(job, profile, config)
    subject, body = composed.subject, composed.body
    print(
        f"  [confidence] {composed.confidence.score}% "
        f"({int(composed.confidence.fact_ratio * 100)}% fact-based) "
        f"persona={composed.persona} structure={'→'.join(composed.structure)}"
    )
    track = job.get("track", "python")
    resume: Path | None = None
    if templates.should_attach_resume(job, config):
        resume_rel = config.get("resume_paths", {}).get(track, "")
        if resume_rel:
            resume = Path(__file__).resolve().parent.parent / resume_rel

    ok = send_email(to, subject, body, resume)
    meta = composed.meta_json() if ok else None
    return ok, meta


def send_followup(job: dict[str, Any], followup_num: int, config: dict | None = None) -> tuple[bool, str | None]:
    profile = _profile()
    to = job.get("contact_email")
    if not to:
        to, _ = resolve_contact_email(job, config)
    if not to:
        return False, None
    if config is None:
        from job_radar.daily import load_config

        config = load_config()
    composed = compose_followup(job, profile, followup_num, config)
    subject, body = composed.subject, composed.body
    track = job.get("track", "python")
    resume: Path | None = None
    resume_rel = (config or {}).get("resume_paths", {}).get(track, "")
    if resume_rel:
        resume = Path(__file__).resolve().parent.parent / resume_rel
    ok = send_email(to, subject, body, resume)
    return ok, composed.meta_json() if ok else None


def send_to_manual_contact(
    job: dict[str, Any],
    contact: dict[str, Any],
    config: dict,
) -> tuple[bool, str | None]:
    """Send outreach to a user-added contact (from LinkedIn research)."""
    from job_radar import database
    from job_radar.email_finder import classify_audience

    to = contact.get("email")
    if not to:
        return False, None

    payload = {
        **job,
        "contact_email": to,
        "contact_name": contact.get("name") or "",
        "outreach_audience": classify_audience(to),
    }
    print(f"  [manual contact] {payload.get('contact_name') or to} → {to}")

    profile = _profile()
    composed = compose_with_meta(payload, profile, config)
    track = job.get("track", "python")
    resume: Path | None = None
    if templates.should_attach_resume(payload, config):
        resume_rel = config.get("resume_paths", {}).get(track, "")
        if resume_rel:
            resume = Path(__file__).resolve().parent.parent / resume_rel

    ok = send_email(to, composed.subject, composed.body, resume)
    meta = composed.meta_json() if ok else None
    if ok and contact.get("id"):
        database.mark_contact_email_sent(contact["id"], meta)
    return ok, meta
