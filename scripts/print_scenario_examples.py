"""Print one composed email per outreach scenario (dry-run, no SMTP)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from job_radar.outreach_engine import compose_followup, compose_with_meta

profile = {
    "YOUR_NAME": os.getenv("YOUR_NAME", "Divyansh Singh"),
    "GITHUB_URL": os.getenv("GITHUB_URL", "https://github.com/Divyansnh"),
    "PROJECT_GITHUB_URL": os.getenv(
        "PROJECT_GITHUB_URL", "https://github.com/Divyansnh/expiry_tracker_final"
    ),
    "DEMO_VIDEO_URL": os.getenv(
        "DEMO_VIDEO_URL", "https://www.youtube.com/watch?v=Dge_LY-7zbg"
    ),
    "LINKEDIN_URL": os.getenv("LINKEDIN_URL", ""),
}
cfg = {
    "outreach": {
        "personalization_level": 1,
        "attach_resume_decision_maker": True,
        "attach_resume_recruiter": True,
    }
}


def show(title: str, composed, attach: str) -> None:
    sep = "=" * 72
    print(sep)
    print(title)
    print(
        f"Persona: {composed.persona} | Archetype: {composed.archetype} | "
        f"Structure: {' -> '.join(composed.structure)}"
    )
    print(f"Attachment: {attach} | Confidence: {composed.confidence.score}%")
    print(f"SUBJECT: {composed.subject}")
    print("-" * 72)
    print(composed.body)
    print()


def main() -> None:
    # --- Initial emails ---
    show(
        "1. Decision maker | Python | startup_small",
        compose_with_meta(
            {
                "company": "StealthPay",
                "title": "Junior Python Developer",
                "track": "python",
                "description": "YC startup. FastAPI PostgreSQL REST API microservices AWS.",
                "contact_email": "founder@stealthpay.io",
                "outreach_audience": "decision_maker",
                "status": "new",
            },
            profile,
            {**cfg, "outreach": {**cfg["outreach"], "seed": 10}},
        ),
        "No resume",
    )

    show(
        "2. Decision maker | SQL/DBA | enterprise",
        compose_with_meta(
            {
                "company": "Infosys",
                "title": "Junior Database Engineer",
                "track": "sql_dba",
                "description": "PostgreSQL backup restore replication ETL migration 24/7 on-call.",
                "contact_email": "rajesh.kumar@infosys.com",
                "outreach_audience": "decision_maker",
                "status": "new",
            },
            profile,
            {**cfg, "outreach": {**cfg["outreach"], "seed": 20}},
        ),
        "No resume",
    )

    show(
        "3. Decision maker | Python | Series A | already applied",
        compose_with_meta(
            {
                "company": "FinStack",
                "title": "Backend Engineer",
                "track": "python",
                "description": "Series A fintech. FastAPI Django PostgreSQL APIs ETL.",
                "contact_email": "cto@finstack.io",
                "outreach_audience": "decision_maker",
                "status": "applied",
                "applied_at": "2026-07-01T10:00:00+00:00",
            },
            profile,
            {**cfg, "outreach": {**cfg["outreach"], "seed": 30}},
        ),
        "No resume",
    )

    show(
        "4. Recruiter | Python",
        compose_with_meta(
            {
                "company": "Razorpay",
                "title": "Python Developer",
                "track": "python",
                "description": "Python FastAPI Flask PostgreSQL AWS APIs.",
                "contact_email": "careers@razorpay.com",
                "outreach_audience": "recruiter",
                "status": "new",
            },
            profile,
            {**cfg, "outreach": {**cfg["outreach"], "seed": 40}},
        ),
        "Resume attached (resume_python_junior.pdf)",
    )

    show(
        "5. Recruiter | SQL/DBA | already applied",
        compose_with_meta(
            {
                "company": "BankCo",
                "title": "Junior SQL DBA",
                "track": "sql_dba",
                "description": "SQL Server backup restore indexing replication T-SQL.",
                "contact_email": "hr@bankco.com",
                "outreach_audience": "recruiter",
                "status": "applied",
                "applied_at": "2026-06-28T10:00:00+00:00",
            },
            profile,
            {**cfg, "outreach": {**cfg["outreach"], "seed": 50}},
        ),
        "Resume attached (resume_sql_dba_junior.pdf)",
    )

    show(
        "6. Decision maker | Python | growth_saas",
        compose_with_meta(
            {
                "company": "DataPipe",
                "title": "Python Backend Engineer",
                "track": "python",
                "description": "Mid-size SaaS. Python backend PostgreSQL microservices API.",
                "contact_email": "eng-lead@datapipe.com",
                "outreach_audience": "decision_maker",
                "status": "new",
            },
            profile,
            {**cfg, "outreach": {**cfg["outreach"], "seed": 60}},
        ),
        "No resume",
    )

    base_dm = {
        "company": "Acuity Analytics",
        "title": "Python Developer",
        "track": "python",
        "description": "FastAPI Flask APIs PostgreSQL.",
        "contact_email": "nihal.upadhyay@acuityanalytics.com",
        "outreach_audience": "decision_maker",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    base_sql = {
        "company": "DataVault",
        "title": "PostgreSQL DBA",
        "track": "sql_dba",
        "description": "PostgreSQL backup restore ETL replication on-call 24/7.",
        "contact_email": "dba-lead@datavault.com",
        "outreach_audience": "decision_maker",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }
    base_rec = {
        "company": "HireCo",
        "title": "Python Dev",
        "track": "python",
        "description": "Python FastAPI APIs.",
        "contact_email": "talent@hireco.com",
        "outreach_audience": "recruiter",
        "initial_email_sent_at": "2026-07-01T10:00:00+00:00",
    }

    followups = [
        ("7a. Follow-up #1 (day 3) | Decision maker | Python", base_dm, 1, "No resume"),
        ("7b. Follow-up #2 (day 7) | Decision maker | Python", base_dm, 2, "Offers to send resume"),
        ("7c. Follow-up #3 (day 12) | Decision maker | Python — close", base_dm, 3, "No resume"),
        ("8a. Follow-up #1 (day 3) | Decision maker | SQL/DBA", base_sql, 1, "No resume"),
        ("8b. Follow-up #2 (day 7) | Decision maker | SQL/DBA", base_sql, 2, "Offers to send resume"),
        ("9. Follow-up #2 (day 7) | Recruiter", base_rec, 2, "Says resume still attached from email 1"),
    ]
    for title, job, n, attach in followups:
        show(
            title,
            compose_followup(job, profile, n, {**cfg, "outreach": {**cfg["outreach"], "seed": 70 + n}}),
            attach,
        )


if __name__ == "__main__":
    main()
