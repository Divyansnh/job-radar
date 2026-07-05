"""Save a logged-in browser session for Playwright portal scraping.

Usage:
  python scripts/save_browser_session.py naukri
  python scripts/save_browser_session.py hirist

A browser window opens. Log in manually, then press Enter in this terminal to save the session.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="Save Playwright login session for a job portal")
    parser.add_argument("portal", choices=["naukri", "hirist"], help="Portal to log into")
    args = parser.parse_args()

    cfg_path = ROOT / "browser_portals.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        portals = (yaml.safe_load(f) or {}).get("portals", {})

    portal_cfg = portals.get(args.portal)
    if not portal_cfg:
        print(f"Unknown portal: {args.portal}")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install browser deps first:")
        print("  pip install -r requirements-browser.txt")
        print("  playwright install chromium")
        return 1

    state_rel = portal_cfg.get("state_file", f"secrets/{args.portal}_state.json")
    state_path = ROOT / state_rel
    state_path.parent.mkdir(parents=True, exist_ok=True)
    login_url = portal_cfg.get("login_url", "")

    print(f"Opening {args.portal} login page...")
    print("1. Log in fully in the browser window")
    print("2. Complete any captcha if shown")
    print("3. Return here and press Enter to save the session")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        input("Press Enter after you are logged in... ")
        context.storage_state(path=str(state_path))
        browser.close()

    print(f"Saved session to {state_path}")
    print("Daily runs will reuse this until it expires (re-save if scrapes start failing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
