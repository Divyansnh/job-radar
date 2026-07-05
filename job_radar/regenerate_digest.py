"""Regenerate output/digest.html from the tracker DB (no scrape).

Usage: python -m job_radar.regenerate_digest
"""

from __future__ import annotations

from job_radar import database, digest
from job_radar.daily import ROOT, load_config


def main() -> None:
    config = load_config()
    limit = config.get("daily_job_limit", 10)
    queue = database.get_todays_queue(limit, config)
    stats = database.stats()
    out = ROOT / "output" / "digest.html"
    digest.write_digest(queue, stats, out)
    print(f"Wrote {len(queue)} jobs to {out}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
