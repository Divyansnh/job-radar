"""Send outreach for exactly one job by database id (live SMTP test)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send outreach email for one job")
    parser.add_argument("job_id", type=int, help="Database job id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve email and print preview only; do not send",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    from job_radar import database, emailer, templates
    from job_radar.daily import load_config
    from job_radar.email_finder import classify_audience

    database.init_db()
    job = database.get_job(args.job_id)
    if not job:
        print(f"ERROR: No job with id={args.job_id}")
        return 1

    config = load_config()
    followup_days = config.get("followup_days", [3, 7, 12])

    to, source = emailer.resolve_contact_email(job)
    print(f"Job #{job['id']}: {job['company']} — {job['title']}")
    print(f"Track: {job.get('track')} | Score: {job.get('score')} | Status: {job.get('outreach_status')}")
    print(f"Contact: {to or '(none)'} via {source}")

    if not to:
        print("ERROR: No contact email found for this job.")
        return 1

    if not job.get("contact_email"):
        job["contact_email"] = to
        job["outreach_audience"] = classify_audience(to)

    profile = {
        "YOUR_NAME": os.getenv("YOUR_NAME", ""),
        "GITHUB_URL": os.getenv("GITHUB_URL", ""),
        "LOOM_URL": os.getenv("LOOM_URL", ""),
        "LINKEDIN_URL": os.getenv("LINKEDIN_URL", ""),
    }
    composed = templates.compose_with_meta(job, profile, config)
    print(f"\nPersona: {composed.persona} | Archetype: {composed.archetype}")
    print(f"Structure: {' -> '.join(composed.structure)}")
    print(composed.confidence.format_summary())
    print(f"\nSubject: {composed.subject}")
    print("-" * 40)
    print(composed.body)
    print("-" * 40)

    if args.dry_run:
        print("\n[DRY RUN] Email not sent.")
        return 0

    if job.get("outreach_status") != "pending":
        print(f"\nWARNING: outreach_status is '{job.get('outreach_status')}', not pending.")
        print("Sending anyway for this one-off test...")

    print("\n[Sending...]")
    ok, meta = emailer.send_initial_outreach(job, config)
    if ok:
        database.mark_email_sent(job["id"], followup_days, meta)
        print(f"SUCCESS: Email sent to {to}")
        return 0

    print("FAILED: send_initial_outreach returned False (check SMTP config).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
