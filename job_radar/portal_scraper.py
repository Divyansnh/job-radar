"""Tier 2: Job portal scraping via JobSpy."""

from __future__ import annotations

from typing import Any


def _scrape_one(
    portal: str,
    term: str,
    location: str,
    hours_old: int,
    results_wanted: int,
) -> list[dict[str, Any]]:
    from jobspy import scrape_jobs

    df = scrape_jobs(
        site_name=[portal],
        search_term=term,
        location=location,
        results_wanted=results_wanted,
        hours_old=hours_old,
        country_indeed="India",
        linkedin_fetch_description=True,
    )
    if df is None or df.empty:
        return []

    jobs: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        jobs.append(
            {
                "company": str(row.get("company", "") or ""),
                "title": str(row.get("title", "") or ""),
                "location": str(row.get("location", "") or location),
                "job_url": str(row.get("job_url", "") or row.get("link", "") or ""),
                "description": str(row.get("description", "") or ""),
                "posted_at": str(row.get("date_posted", "") or ""),
                "source": str(row.get("site", portal)),
            }
        )
    return jobs


def scrape_portals(config: dict) -> list[dict[str, Any]]:
    try:
        import jobspy  # noqa: F401
    except ImportError:
        print("  [warn] python-jobspy not installed — skipping portals")
        return []

    primary_portals = config.get("portals", ["linkedin", "google"])
    optional_portals = config.get("optional_portals", [])
    portals = primary_portals + [p for p in optional_portals if p not in primary_portals]

    hours_old = config.get("max_age_days", 14) * 24
    locations = config.get("search_locations", ["Hyderabad", "India"])
    results_wanted = config.get("portal_results_per_search", 15)
    all_jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    search_config = config.get("search_terms", {})
    for track, terms in search_config.items():
        for term in terms:
            for location in locations:
                for portal in portals:
                    optional = portal in optional_portals
                    try:
                        batch = _scrape_one(portal, term, location, hours_old, results_wanted)
                    except Exception as exc:
                        label = "optional, skipped" if optional else "failed"
                        print(f"  [warn] {portal} '{term}' ({location}): {label} — {exc}")
                        continue

                    added = 0
                    for job in batch:
                        url = job.get("job_url", "")
                        if url and url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)
                        job["track"] = track
                        all_jobs.append(job)
                        added += 1

                    if added:
                        print(f"  [ok] {portal} '{term}' ({location}): {added} roles")

    return all_jobs
