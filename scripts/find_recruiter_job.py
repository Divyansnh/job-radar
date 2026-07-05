"""Scan DB for one pending job with a resolvable recruiter email."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from job_radar import email_finder  # noqa: E402

conn = sqlite3.connect(ROOT / "data" / "tracker.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT id, company, title, track, outreach_status, score, description, job_url
    FROM jobs
    WHERE outreach_status = 'pending'
    ORDER BY score DESC
    """
).fetchall()

print(f"Scanning {len(rows)} pending jobs...\n")

for r in rows:
    job = dict(r)
    desc = job.get("description") or ""
    in_desc = email_finder.emails_in_text(desc)
    email, source = email_finder.find_contact_email(
        job["company"], desc, job.get("job_url")
    )
    if email and source == "description":
        print(f"*** BEST: id={job['id']} {job['company']} | {email} ({source})")
        print(f"    {job['title']} | score={job['score']} | track={job['track']}")
    elif email and source == "hunter":
        print(f"HUNTER: id={job['id']} {job['company']} | {email} ({source})")
    elif in_desc:
        print(f"RAW IN DESC: id={job['id']} {job['company']} | {in_desc[:2]}")

print("\n--- Top guess-only candidates (careers@) ---")
for r in rows[:20]:
    job = dict(r)
    email, source = email_finder.find_contact_email(
        job["company"], job.get("description", ""), job.get("job_url"), use_hunter=False
    )
    if email:
        print(f"id={job['id']} {job['company']}: {email} ({source})")
