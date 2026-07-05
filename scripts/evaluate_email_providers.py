"""Spike: evaluate email discovery strategies before implementing the waterfall.

Usage:
  .venv\\Scripts\\python.exe scripts/evaluate_email_providers.py
  .venv\\Scripts\\python.exe scripts/evaluate_email_providers.py --live-hunter
  .venv\\Scripts\\python.exe scripts/evaluate_email_providers.py --scrape --limit 15

Does NOT change production code. Reports hit rates per tier on jobs in tracker.db.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from job_radar import database, email_finder  # noqa: E402

_USER_AGENT = "JobRadar-EmailEval/1.0 (+local research; contact via job posting only)"
_CAREERS_PATHS = ("/careers", "/jobs", "/contact", "/about", "/join-us", "/work-with-us")
_IN_LOCALS = ("careers", "jobs", "hr", "hiring", "talent", "recruitment", "recruit", "people")


@dataclass
class TierResult:
    tier: str
    email: str | None
    detail: str = ""
    used_api_credit: bool = False


@dataclass
class JobEval:
    job_id: int
    company: str
    title: str
    score: float
    job_url: str
    stored_email: str | None
    tiers: list[TierResult] = field(default_factory=list)
    best: TierResult | None = None

    def pick_best(self, order: list[str]) -> None:
        rank = {name: i for i, name in enumerate(order)}
        hits = [t for t in self.tiers if t.email]
        if not hits:
            self.best = None
            return
        hits.sort(key=lambda t: rank.get(t.tier, 99))
        self.best = hits[0]


def _slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]", "", company.lower())


def _domain_candidates(company: str, job_url: str | None) -> list[str]:
    domains: list[str] = []
    from_url = email_finder.domain_from_job_url(job_url)
    if from_url:
        domains.append(from_url)

    slug = _slug(company)
    if slug:
        for tld in ("com", "in", "io", "co"):
            domains.append(f"{slug}.{tld}")
        # common Indian IT suffix patterns
        domains.append(f"{slug}tech.com")

    seen: set[str] = set()
    out: list[str] = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _rank_email(email: str) -> int:
    local = email.split("@", 1)[0].lower()
    score = 0
    if any(x in local for x in _IN_LOCALS):
        score += 30
    if email_finder.classify_audience(email) == "decision_maker":
        score += 10
    return score


def tier_stored(job: dict[str, Any]) -> TierResult:
    email = job.get("contact_email")
    return TierResult("stored", email, "already in DB" if email else "empty")


def tier_jd(description: str) -> TierResult:
    emails = email_finder.emails_in_text(description or "")
    if not emails:
        return TierResult("jd", None, "no @ in description")
    best = max(emails, key=_rank_email)
    return TierResult("jd", best, f"{len(emails)} found in text")


def tier_hunter(company: str, job_url: str | None, *, live: bool) -> TierResult:
    if not live:
        key = __import__("os").getenv("HUNTER_API_KEY")
        if not key:
            return TierResult("hunter", None, "skip (no HUNTER_API_KEY)")
        return TierResult("hunter", None, "dry-run (pass --live-hunter to spend credit)")

    domain = email_finder.domain_from_job_url(job_url)
    email = email_finder.hunter_domain_search(domain=domain) if domain else None
    if email:
        return TierResult("hunter", email, f"domain={domain}", used_api_credit=True)
    email = email_finder.hunter_domain_search(company=company)
    if email:
        return TierResult("hunter", email, "company search", used_api_credit=True)
    return TierResult("hunter", None, "no result", used_api_credit=True)


def _fetch_html(url: str, timeout: int = 8) -> str:
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": _USER_AGENT},
        allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def tier_website_scrape(company: str, job_url: str | None, *, enabled: bool) -> TierResult:
    if not enabled:
        return TierResult("scrape", None, "skip (--scrape to enable)")

    candidates = _domain_candidates(company, job_url)
    found: list[str] = []
    tried: list[str] = []

    for domain in candidates[:4]:
        for path in _CAREERS_PATHS:
            url = f"https://{domain}{path}"
            tried.append(url)
            try:
                html = _fetch_html(url)
            except requests.RequestException:
                continue
            for email in email_finder.emails_in_text(html):
                if domain in email.lower():
                    found.append(email)
            if found:
                best = max(found, key=_rank_email)
                return TierResult("scrape", best, f"from {url}")
            time.sleep(0.4)

    return TierResult("scrape", None, f"tried {len(tried)} URLs, 0 emails")


def tier_pattern(domain: str | None) -> TierResult:
    """Pattern on a real domain (not slug.com guess). No SMTP verify in spike."""
    if not domain:
        return TierResult("pattern", None, "no domain")
    for local in ("careers", "jobs", "hr", "talent", "hiring", "recruitment"):
        email = f"{local}@{domain}"
        return TierResult("pattern", email, f"inferred {local}@ on resolved domain")
    return TierResult("pattern", None, "no pattern")


def tier_guess_legacy(company: str) -> TierResult:
    email = email_finder.guess_contact_email(company, "")
    return TierResult("guess", email, "careers@slug.com (current fallback)")


def evaluate_job(job: dict[str, Any], *, live_hunter: bool, scrape: bool) -> JobEval:
    desc = job.get("description") or ""
    ev = JobEval(
        job_id=job["id"],
        company=job["company"],
        title=job["title"],
        score=float(job.get("score") or 0),
        job_url=job.get("job_url") or "",
        stored_email=job.get("contact_email"),
    )

    ev.tiers.append(tier_stored(job))
    ev.tiers.append(tier_jd(desc))
    ev.tiers.append(tier_website_scrape(job["company"], job.get("job_url"), enabled=scrape))

    domain = email_finder.domain_from_job_url(job.get("job_url"))
    if domain:
        ev.tiers.append(tier_pattern(domain))

    ev.tiers.append(tier_hunter(job["company"], job.get("job_url"), live=live_hunter))
    ev.tiers.append(tier_guess_legacy(job["company"]))

    order = ["stored", "jd", "scrape", "pattern", "hunter", "guess"]
    ev.pick_best(order)
    return ev


def summarize(results: list[JobEval]) -> dict[str, Any]:
    by_tier: dict[str, int] = {}
    for r in results:
        if r.best:
            by_tier[r.best.tier] = by_tier.get(r.best.tier, 0) + 1
    api_credits = sum(1 for r in results for t in r.tiers if t.used_api_credit and t.email)
    return {
        "jobs_evaluated": len(results),
        "with_any_email": sum(1 for r in results if r.best and r.best.email),
        "best_source_counts": by_tier,
        "hunter_credits_used": api_credits,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate email discovery tiers on tracker DB")
    parser.add_argument("--limit", type=int, default=0, help="Max jobs (0 = all pending)")
    parser.add_argument("--live-hunter", action="store_true", help="Spend Hunter credits (careful)")
    parser.add_argument("--scrape", action="store_true", help="HTTP-scrape company career pages")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    parser.add_argument("--status", default="pending", help="Job outreach_status filter")
    args = parser.parse_args()

    database.init_db()
    jobs = database.list_jobs(pending_outreach=(args.status == "pending"), limit=500)
    if args.status not in ("pending", ""):
        jobs = database.list_jobs(outreach_status=args.status, limit=500)
    if args.limit:
        jobs = jobs[: args.limit]

    if not jobs:
        print("No jobs to evaluate.")
        return 1

    print(f"Evaluating {len(jobs)} jobs (live_hunter={args.live_hunter}, scrape={args.scrape})\n")
    results: list[JobEval] = []
    for job in jobs:
        full = database.get_job(job["id"]) or job
        ev = evaluate_job(full, live_hunter=args.live_hunter, scrape=args.scrape)
        results.append(ev)
        best = ev.best
        label = f"{best.tier}:{best.email}" if best and best.email else "NONE"
        print(f"#{ev.job_id:3} {ev.company[:28]:28} | best={label}")

    summary = summarize(results)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))

    if args.json:
        out = ROOT / "data" / "email_eval_latest.json"
        out.parent.mkdir(exist_ok=True)
        payload = {
            "summary": summary,
            "jobs": [
                {
                    **{k: v for k, v in asdict(r).items() if k != "tiers"},
                    "tiers": [asdict(t) for t in r.tiers],
                }
                for r in results
            ],
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {out}")

    if args.live_hunter:
        print("\nWARNING: Hunter credits may have been consumed. Check hunter.io dashboard.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
