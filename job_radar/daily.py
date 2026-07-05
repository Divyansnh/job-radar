"""Main daily pipeline — run with: python -m job_radar.daily"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    for name in ("config.yaml", "config.example.yaml"):
        path = ROOT / name
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    print("ERROR: No config.yaml found. Copy config.example.yaml to config.yaml")
    sys.exit(1)


def load_companies() -> list[dict]:
    path = ROOT / "companies.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("companies", [])


def run() -> None:
    load_dotenv(ROOT / ".env")
    config = load_config()
    followup_days = config.get("followup_days", [3, 7, 12])
    daily_limit = config.get("daily_job_limit", 10)

    from job_radar import ats_fetcher, database, digest, emailer, portal_scraper, scorer

    print("=" * 50)
    print("Job Radar — daily run")
    print("=" * 50)

    database.init_db()

    # --- Tier 1: Company career pages (Greenhouse / Lever / Ashby) ---
    print("\n[Tier 1] Company ATS APIs (companies.yaml)...")
    companies = load_companies()
    company_jobs = ats_fetcher.fetch_all_companies(companies)
    print(f"  Found {len(company_jobs)} roles from {len(companies)} company career pages")

    # --- Tier 2: Job portals (LinkedIn, Google, optional Naukri) ---
    portal_list = config.get("portals", []) + config.get("optional_portals", [])
    print(f"\n[Tier 2] Job portals ({', '.join(portal_list)})...")
    portal_jobs = portal_scraper.scrape_portals(config)
    print(f"  Found {len(portal_jobs)} roles from portals (JobSpy)")

    from job_radar.browser_scraper import scrape_browser_portals

    browser_jobs = scrape_browser_portals(config, ROOT)
    print(f"  Found {len(browser_jobs)} roles from browser portals (Playwright)")
    portal_jobs = portal_jobs + browser_jobs

    # --- Merge, score, dedupe ---
    all_jobs = company_jobs + portal_jobs
    ranked = scorer.filter_and_rank(all_jobs, config)
    print(f"\n[Filter] {len(ranked)} jobs passed score >= {config.get('min_score', 70)}")

    new_count = 0
    for job in ranked:
        if database.insert_job(job) is not None:
            new_count += 1
    print(f"[Tracker] {new_count} new jobs added to database")

    # --- Today's queue ---
    queue = database.get_todays_queue(daily_limit, config)
    print(f"\n[Queue] Top {len(queue)} jobs for today")

    # --- Send initial outreach ---
    print("\n[Email] Sending initial outreach...")
    for job in queue:
        if job.get("outreach_status") == "pending":
            ok, meta = emailer.send_initial_outreach(job, config)
            if ok:
                database.mark_email_sent(job["id"], followup_days, meta)
                print(f"  Sent → {job['company']}: {job['title']}")

    # --- Send due follow-ups ---
    print("\n[Email] Processing follow-ups...")
    for job in database.get_due_followups():
        n = job.get("followup_count", 0) + 1
        ok, meta = emailer.send_followup(job, n, config)
        if ok:
            database.mark_followup_sent(job["id"], n, followup_days, meta)
            print(f"  Follow-up #{n} → {job['company']}")

    # --- Write digest ---
    out = ROOT / "output" / "digest.html"
    stats = database.stats()
    digest.write_digest(queue, stats, out)
    manual = ROOT / "manual_search.yaml"
    if manual.exists():
        print(f"\n[Manual] Portals/employers to check yourself: {manual}")
    print(f"\n[Done] Open digest: {out}")
    print(f"       Stats: {stats}")


if __name__ == "__main__":
    run()
