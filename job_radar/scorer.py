"""Score and filter jobs — title + full JD, location-aware, profile-tuned."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Seniority signals in full job description (not just title)
_SENIOR_DESC = re.compile(
    r"(?:\b(?:senior|lead|principal|staff|architect|director|manager|head of)\b|"
    r"\b(?:minimum|min\.?|at least)\s*(\d+)\s*\+?\s*years|"
    r"\b(\d+)\s*\+\s*years|\b(\d+)\s*[-–to]+\s*(\d+)\s*years|"
    r"\bmentor(?:ing)?\b|\blead(?:ing)?\s+a\s+team\b|\bpeople\s+management\b)",
    re.I,
)

_JUNIOR_DESC = re.compile(
    r"\b(?:junior|entry[\s-]?level|associate|fresher|graduate|intern|trainee|"
    r"0\s*[-–to]+\s*2\s*years?|1\s*[-–to]+\s*2\s*years?|"
    r"no\s+prior\s+experience|freshers?\s+welcome)\b",
    re.I,
)

_AI_ML_DESC = re.compile(
    r"\b(?:machine\s+learning|deep\s+learning|pytorch|tensorflow|keras|"
    r"\bllm\b|langchain|hugging\s*face|\bnlp\b|natural\s+language\s+processing|"
    r"computer\s+vision|generative\s+ai|ai/ml|ml\s+engineer|"
    r"build(?:ing)?\s+(?:ml|ai)\s+models?)\b",
    re.I,
)

_BI_REQUIRED = re.compile(
    r"(?:required|must\s+have|proficien(?:t|cy)|expert|hands[\s-]on|experience\s+with).{0,50}"
    r"(?:power\s*bi|tableau|looker|qlik)",
    re.I,
)

_DATABASE_DESC = re.compile(
    r"\b(?:postgresql|postgres|sql\s+server|stored\s+procedur|database\s+migrat|"
    r"\betl\b|plpgsql|t-?sql|aurora|dba|database\s+administrator|"
    r"query\s+optimiz|backup\s+and\s+restore|indexing|replication|"
    r"informatica|data\s+migrat)\b",
    re.I,
)

_PYTHON_BACKEND_DESC = re.compile(
    r"\b(?:python|flask|fastapi|django|rest\s*api|backend\s+api|"
    r"node\.?js|aws\s+lambda)\b",
    re.I,
)

_AMBIGUOUS_TITLE = re.compile(
    r"^(?:software|backend|full[\s-]?stack|data|platform|cloud|"
    r"application|technology)\s+(?:engineer|developer|analyst|associate)\s*$",
    re.I,
)


def normalize_key(company: str, title: str, location: str = "") -> str:
    c = re.sub(r"[^a-z0-9]", "", company.lower())
    t = re.sub(r"[^a-z0-9]", "", title.lower())
    l = re.sub(r"[^a-z0-9]", "", (location or "").lower())
    return f"{c}|{t}|{l}"


def _parse_posted(posted_at: Any) -> datetime | None:
    if posted_at is None:
        return None
    if isinstance(posted_at, datetime):
        return posted_at if posted_at.tzinfo else posted_at.replace(tzinfo=timezone.utc)
    if isinstance(posted_at, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                return datetime.strptime(
                    posted_at.replace("+00:00", "Z"), fmt
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def age_days(posted_at: Any) -> int | None:
    dt = _parse_posted(posted_at)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).days


def text_excluded(text: str, exclude_words: list[str]) -> bool:
    t = text.lower()
    for word in exclude_words:
        w = re.escape(word.lower())
        if re.search(rf"\b{w}\b", t):
            return True
    return False


def title_excluded(title: str, exclude_words: list[str]) -> bool:
    return text_excluded(title, exclude_words)


def _min_years_required(text: str) -> int | None:
    """Extract minimum years if stated; None if not mentioned."""
    for m in _SENIOR_DESC.finditer(text):
        g = m.groups()
        for val in g:
            if val and val.isdigit():
                return int(val)
        if m.group(0) and any(
            w in m.group(0).lower()
            for w in ("senior", "lead", "principal", "architect", "director", "manager")
        ):
            return 5
    range_m = re.search(r"\b(\d+)\s*[-–to]+\s*(\d+)\s*years", text, re.I)
    if range_m:
        return int(range_m.group(1))
    return None


def description_rejected(title: str, description: str, config: dict) -> str | None:
    """Return rejection reason or None if JD looks acceptable."""
    combined = f"{title}\n{description}"
    lower = combined.lower()

    if text_excluded(combined, config.get("title_exclude", [])):
        return "excluded keyword"

    if _AI_ML_DESC.search(combined):
        return "ai/ml role"

    if _BI_REQUIRED.search(description or title):
        return "bi tools required"

    min_years = _min_years_required(combined)
    max_accept = config.get("max_acceptable_years", 2)
    if min_years is not None and min_years > max_accept:
        return f"requires {min_years}+ years"

    # Title says junior but description demands senior experience
    title_junior = bool(re.search(r"\b(?:junior|fresher|entry|associate|intern)\b", title, re.I))
    if title_junior and min_years is not None and min_years >= 3:
        return "junior title, senior JD"

    if _SENIOR_DESC.search(description) and not _JUNIOR_DESC.search(description):
        if not title_junior and min_years is None:
            # Ambiguous: no years stated but senior language only — penalize later, don't hard reject
            pass

    # Ambiguous title: must have profile signals in description
    if _AMBIGUOUS_TITLE.search(title.strip()):
        if not (_DATABASE_DESC.search(description) or _PYTHON_BACKEND_DESC.search(description)):
            return "ambiguous title, weak JD fit"

    # Data analyst: allow only python+sql style (no BI)
    if re.search(r"\bdata\s+analyst\b", title, re.I):
        if _BI_REQUIRED.search(description):
            return "bi analyst role"
        if not (_PYTHON_BACKEND_DESC.search(description) and re.search(r"\bsql\b", lower)):
            return "analyst without python+sql"

    return None


def location_tier(location: str, config: dict) -> int:
    """0 = best (Hyderabad), 1 = secondary cities, 2 = other India, 3 = unknown."""
    loc = (location or "").lower()
    if not loc:
        return 3

    primary = config.get("location_priority", {}).get("primary", "Hyderabad").lower()
    if primary in loc or "hyderabad" in loc:
        return 0

    secondary = [c.lower() for c in config.get("location_priority", {}).get("secondary", [])]
    for city in secondary:
        if city in loc:
            return 1

    if any(k in loc for k in ("india", "remote", "wfh", "work from home", "pan india")):
        return 2

    return 3


def skill_overlap(description: str, skills: list[str]) -> float:
    if not description:
        return 0.0
    d = description.lower()
    hits = sum(1 for s in skills if s.lower() in d)
    return hits / max(len(skills), 1)


def _infer_track(title: str, description: str, default: str) -> str:
    """Re-classify track from JD when title is vague."""
    combined = f"{title} {description}".lower()
    db_score = len(_DATABASE_DESC.findall(combined))
    py_score = len(_PYTHON_BACKEND_DESC.findall(combined))

    if db_score >= py_score + 2 or re.search(r"\b(?:dba|database\s+admin)\b", combined):
        return "sql_dba"
    if py_score > 0:
        return "python"
    return default


def score_job(job: dict[str, Any], config: dict) -> float:
    title = job.get("title", "")
    desc = job.get("description", "") or ""
    track = job.get("track", "python")

    reject = description_rejected(title, desc, config)
    if reject:
        job["reject_reason"] = reject
        job["score"] = 0.0
        return 0.0

    track = _infer_track(title, desc, track)
    job["track"] = track

    max_age = config.get("max_age_days", 14)
    days = age_days(job.get("posted_at"))
    if days is not None and days > max_age:
        job["score"] = 0.0
        return 0.0

    score = 0.0
    combined = f"{title} {desc}"
    t = title.lower()

    # Role match (0-35)
    if track == "sql_dba" and (
        any(k in t for k in ("sql", "dba", "database", "etl", "migration"))
        or _DATABASE_DESC.search(desc)
    ):
        score += 35
    elif track == "python" and ("python" in t or _PYTHON_BACKEND_DESC.search(desc)):
        score += 30
    elif any(k in t for k in ("junior", "associate", "entry", "fresher", "intern")):
        score += 20
    elif _DATABASE_DESC.search(desc):
        score += 25

    # Profile fit from JD (0-25) — database work is top priority
    if _DATABASE_DESC.search(desc):
        score += 25
    elif _PYTHON_BACKEND_DESC.search(desc) and re.search(r"\bsql\b", desc, re.I):
        score += 15
    elif _PYTHON_BACKEND_DESC.search(desc):
        score += 8

    # Seniority from JD when years not explicit (0-15)
    min_years = _min_years_required(combined)
    if min_years is None:
        if _JUNIOR_DESC.search(combined):
            score += 15
        elif not _SENIOR_DESC.search(desc):
            score += 8  # no years stated, no senior language — plausible junior fit
    elif min_years <= config.get("max_acceptable_years", 2):
        score += 12

    # Freshness (0-15)
    if days is None:
        score += 5
    elif days <= 3:
        score += 15
    elif days <= 7:
        score += 10
    elif days <= 14:
        score += 5

    # Skill overlap (0-15)
    skills = config.get("skills", {}).get(track, [])
    score += skill_overlap(desc, skills) * 15

    # Location (0-15)
    tier = location_tier(job.get("location", ""), config)
    location_bonus = {0: 15, 1: 8, 2: 4, 3: 0}
    score += location_bonus.get(tier, 0)
    job["location_tier"] = tier

    # Source quality (0-10)
    source = job.get("source", "")
    if source in ("greenhouse", "lever", "ashby"):
        score += 10
    elif source in ("linkedin", "hirist", "naukri", "indeed", "glassdoor"):
        score += 7
    else:
        score += 4

    # Track priority boost
    track_boost = config.get("track_priority_boost", {}).get(track, 0)
    score += track_boost

    job["score"] = round(score, 1)
    return job["score"]


def filter_and_rank(jobs: list[dict], config: dict) -> list[dict]:
    min_score = config.get("min_score", 70)
    scored = []
    for job in jobs:
        s = score_job(job, config)
        if s >= min_score:
            job["dedupe_key"] = normalize_key(
                job.get("company", ""),
                job.get("title", ""),
                job.get("location", ""),
            )
            scored.append(job)

    track_order = config.get("track_priority", ["sql_dba", "python"])
    track_rank = {t: i for i, t in enumerate(track_order)}

    def sort_key(j: dict) -> tuple:
        return (
            j.get("location_tier", 3),
            track_rank.get(j.get("track", "python"), 99),
            -j["score"],
            j.get("posted_at") or "",
        )

    scored.sort(key=sort_key)
    return scored


def build_daily_queue(jobs: list[dict], config: dict) -> list[dict]:
    """Pick today's jobs: DBA-first slots, Hyderabad-first within each band."""
    limit = config.get("daily_job_limit", 10)
    slots = config.get("queue_slots", {"sql_dba": 6, "python": 4})
    by_track: dict[str, list[dict]] = {t: [] for t in slots}
    rest: list[dict] = []

    for job in jobs:
        track = job.get("track", "python")
        cap = slots.get(track)
        if cap is not None and len(by_track[track]) < cap:
            by_track[track].append(job)
        else:
            rest.append(job)

    queue: list[dict] = []
    for track in config.get("track_priority", ["sql_dba", "python"]):
        queue.extend(by_track.get(track, []))

    for job in rest:
        if len(queue) >= limit:
            break
        if job not in queue:
            queue.append(job)

    return queue[:limit]
