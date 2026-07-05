"""Setup health check — run without pytest for a quick end-to-end validation.

Usage:
  python -m job_radar.healthcheck           # fast checks (no network)
  python -m job_radar.healthcheck --live    # includes live ATS + portal probe
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def check_python_version() -> bool:
    v = sys.version_info
    ok = v >= (3, 10)
    ( _ok if ok else _fail)(f"Python {v.major}.{v.minor}.{v.micro} (need 3.10+)")
    return ok


def check_dependencies() -> bool:
    required = ["yaml", "dotenv", "requests", "pytest"]
    optional = ["jobspy"]
    all_ok = True
    for mod in required:
        if importlib.util.find_spec(mod.replace("-", "_").split(".")[0]):
            _ok(f"package importable: {mod}")
        else:
            _fail(f"missing package: {mod}")
            all_ok = False
    for mod in optional:
        if importlib.util.find_spec(mod):
            _ok(f"optional package: {mod}")
        else:
            _warn(f"optional missing (portals won't work): {mod}")
    if not all_ok and (ROOT / ".venv").exists():
        venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
        _warn(
            "Dependencies are in .venv — use .\\.venv\\Scripts\\python.exe "
            "or .\\scripts\\healthcheck.bat (not bare `python`)"
        )
        if venv_py.exists():
            _warn(f"Example: {venv_py} -m job_radar.healthcheck --live")
    return all_ok


def check_project_files() -> bool:
    paths = [
        "config.yaml",
        "companies.yaml",
        ".env",
        "job_radar/daily.py",
        "assets",
    ]
    ok = True
    for rel in paths:
        if (ROOT / rel).exists():
            _ok(f"found {rel}")
        else:
            _fail(f"missing {rel}")
            ok = False
    return ok


def check_env_configured() -> bool:
    from dotenv import dotenv_values

    env = dotenv_values(ROOT / ".env")
    placeholders = ("your.email@gmail.com", "your-16-char-app-password", "Your Full Name", "yourusername")
    ok = True
    for key in ("SMTP_USER", "SMTP_PASSWORD", "YOUR_NAME", "GITHUB_URL"):
        val = env.get(key, "")
        if not val or any(p in val for p in placeholders):
            _warn(f".env -> {key} still placeholder (emails won't send)")
            ok = False
        else:
            _ok(f".env -> {key} set")
    return ok


def check_resumes() -> bool:
    import yaml

    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ok = True
    for track, rel in cfg.get("resume_paths", {}).items():
        path = ROOT / rel
        if path.exists():
            _ok(f"resume ({track}): {rel}")
        else:
            _warn(f"resume missing ({track}): {rel}")
            ok = False
    return ok


def check_database_roundtrip() -> bool:
    import gc
    import tempfile

    from job_radar import database
    from job_radar.scorer import normalize_key

    original = database.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            database.DB_PATH = Path(tmp) / "health.db"
            database.init_db()
            job = {
                "dedupe_key": normalize_key("HealthCo", "Junior Python Dev", "India"),
                "company": "HealthCo",
                "title": "Junior Python Dev",
                "location": "India",
                "track": "python",
                "source": "greenhouse",
                "job_url": "https://example.com",
                "score": 80,
            }
            jid = database.insert_job(job)
            assert jid is not None
            _ok("database insert + dedupe")
            gc.collect()
            return True
    except Exception as exc:
        _fail(f"database: {exc}")
        return False
    finally:
        database.DB_PATH = original


def check_scorer_and_digest() -> bool:
    import yaml

    from job_radar.digest import render_digest
    from job_radar.scorer import filter_and_rank

    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    job = {
        "company": "HealthCo",
        "title": "Junior Python Developer",
        "track": "python",
        "source": "greenhouse",
        "job_url": "https://example.com",
        "description": "Python FastAPI PostgreSQL",
        "posted_at": "2026-07-01",
    }
    ranked = filter_and_rank([job], cfg)
    if not ranked:
        _fail("scorer rejected sample junior Python job")
        return False
    _ok(f"scorer passed sample job (score={ranked[0]['score']})")
    html = render_digest(ranked, {"total": 1, "applied": 0, "emailed": 0})
    if "HealthCo" not in html:
        _fail("digest missing company name")
        return False
    _ok("digest HTML renders")
    return True


def check_live_ats() -> bool:
    from job_radar.ats_fetcher import fetch_greenhouse

    jobs = fetch_greenhouse(
        {"name": "Razorpay", "track": "python", "ats": "greenhouse", "token": "razorpay"}
    )
    _ok(f"live ATS (Razorpay): {len(jobs)} open roles fetched")
    return True


def check_live_portal() -> bool:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        _warn("jobspy not installed — skip live portal check")
        return True

    df = scrape_jobs(
        site_name=["naukri"],
        search_term="junior python developer",
        location="India",
        results_wanted=3,
        hours_old=336,
    )
    count = 0 if df is None else len(df)
    _ok(f"live portal (Naukri): {count} results")
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Job Radar setup health check")
    parser.add_argument("--live", action="store_true", help="Include network tests")
    args = parser.parse_args()

    print("=" * 50)
    print("Job Radar Health Check")
    print("=" * 50)

    checks = [
        ("Python version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Project files", check_project_files),
        ("Environment (.env)", check_env_configured),
        ("Resume PDFs", check_resumes),
        ("Database", check_database_roundtrip),
        ("Scorer + digest", check_scorer_and_digest),
    ]
    if args.live:
        checks += [
            ("Live ATS API", check_live_ats),
            ("Live portal scrape", check_live_portal),
        ]

    failed = 0
    for name, fn in checks:
        print(f"\n{name}:")
        try:
            if not fn():
                failed += 1
        except Exception as exc:
            _fail(str(exc))
            failed += 1

    print("\n" + "=" * 50)
    if failed:
        print(f"RESULT: {failed} check group(s) need attention")
        return 1
    print("RESULT: All checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
