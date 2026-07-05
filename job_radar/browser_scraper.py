"""Tier 2b: Browser-based portal scraping via Playwright (logged-in sessions).

Requires one-time login per portal:
  python scripts/save_browser_session.py naukri
  python scripts/save_browser_session.py hirist
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load_browser_portals(root: Path | None = None) -> dict:
    import yaml

    path = (root or ROOT) / "browser_portals.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("portals", {})


def _abs_url(href: str, base: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    base = base.rstrip("/")
    return f"{base}/{href.lstrip('/')}"


def _text(el) -> str:
    try:
        return (el.inner_text() or "").strip()
    except Exception:
        return ""


def _first_text(card, selectors: str) -> str:
    for sel in (s.strip() for s in selectors.split(",") if s.strip()):
        loc = card.locator(sel).first
        if loc.count() > 0:
            t = _text(loc)
            if t:
                return t
    return ""


def _first_href(card, selectors: str, base: str) -> str:
    for sel in (s.strip() for s in selectors.split(",") if s.strip()):
        loc = card.locator(sel).first
        if loc.count() > 0:
            href = loc.get_attribute("href") or ""
            if href:
                return _abs_url(href, base)
    return ""


def _page_blocked(page) -> bool:
    try:
        content = page.content().lower()
    except Exception:
        return True
    blocked = ("recaptcha", "captcha", "unusual traffic", "access denied", "verify you are human")
    return any(b in content for b in blocked)


def _extract_jobs_from_page(page, portal_name: str, portal_cfg: dict, track: str) -> list[dict[str, Any]]:
    sel = portal_cfg.get("selectors", {})
    card_sel = sel.get("job_card", "")
    if not card_sel:
        return []

    base = re.match(r"(https?://[^/]+)", page.url)
    base_url = base.group(1) if base else page.url

    cards = page.locator(card_sel)
    count = cards.count()
    jobs: list[dict[str, Any]] = []
    limit = min(count, 25)

    for i in range(limit):
        card = cards.nth(i)
        title = _first_text(card, sel.get("title", ""))
        if not title:
            continue
        company = _first_text(card, sel.get("company", "")) or "Unknown"
        location = _first_text(card, sel.get("location", ""))
        job_url = _first_href(card, sel.get("title", ""), base_url)
        desc = _first_text(card, sel.get("description", "")) if sel.get("description") else ""

        jobs.append(
            {
                "company": company,
                "title": title,
                "location": location,
                "track": track,
                "source": portal_name,
                "job_url": job_url,
                "description": desc,
                "posted_at": "",
            }
        )

    return jobs


def scrape_browser_portals(config: dict, root: Path | None = None) -> list[dict[str, Any]]:
    """Scrape configured browser portals using saved Playwright sessions."""
    root = root or ROOT
    browser_cfg = config.get("browser_scraping", {})
    if not browser_cfg.get("enabled", True):
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [warn] Playwright not installed — pip install -r requirements-browser.txt")
        print("         Then: playwright install chromium")
        return []

    portals = _load_browser_portals(root)
    if not portals:
        return []

    headless = browser_cfg.get("headless", True)
    slow_mo = browser_cfg.get("slow_mo_ms", 0)
    all_jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)

        for portal_name, portal_cfg in portals.items():
            state_rel = portal_cfg.get("state_file", f"secrets/{portal_name}_state.json")
            state_path = root / state_rel
            if not state_path.exists():
                print(
                    f"  [skip] {portal_name}: no session — run "
                    f"python scripts/save_browser_session.py {portal_name}"
                )
                continue

            context = browser.new_context(storage_state=str(state_path))
            page = context.new_page()

            for search in portal_cfg.get("searches", []):
                url = search.get("url", "")
                track = search.get("track", "python")
                if not url:
                    continue

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2000)

                    if _page_blocked(page):
                        print(
                            f"  [warn] {portal_name}: captcha/block on {url} — "
                            f"re-run save_browser_session.py {portal_name} (logged in)"
                        )
                        continue

                    batch = _extract_jobs_from_page(page, portal_name, portal_cfg, track)
                    added = 0
                    for job in batch:
                        jurl = job.get("job_url", "")
                        if jurl and jurl in seen_urls:
                            continue
                        if jurl:
                            seen_urls.add(jurl)
                        all_jobs.append(job)
                        added += 1

                    if added:
                        print(f"  [ok] {portal_name} (browser): {added} roles from {url}")
                    else:
                        print(f"  [warn] {portal_name}: 0 roles parsed from {url} (selectors may need update)")

                except Exception as exc:
                    print(f"  [warn] {portal_name} browser scrape failed: {exc}")

                time.sleep(browser_cfg.get("delay_seconds", 2))

            context.close()

        browser.close()

    return all_jobs
