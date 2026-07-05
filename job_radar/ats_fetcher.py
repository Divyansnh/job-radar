"""Tier 1: Fetch jobs from company ATS public APIs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests

JUNIOR_PATTERN = re.compile(
    r"junior|entry[\s-]?level|associate|fresher|trainee|0[\s-]?[to\-]?\s?2|"
    r"1[\s-]?[to\-]?\s?3|graduate|intern",
    re.I,
)
SENIOR_PATTERN = re.compile(
    r"senior|lead|principal|staff|architect|director|manager|head of|"
    r"5\+?\s*years|8\+?\s*years|10\+?\s*years",
    re.I,
)


def _parse_date(value: str | int | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.replace("+00:00", "Z"), fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def _is_relevant_title(title: str, track: str) -> bool:
    if SENIOR_PATTERN.search(title):
        return False
    t = title.lower()
    if track == "python":
        if "java" in t or ".net" in t or "c#" in t:
            return False
        return "python" in t or "backend" in t or JUNIOR_PATTERN.search(title) is not None
    if track == "sql_dba":
        return any(k in t for k in ("sql", "dba", "database"))
    return JUNIOR_PATTERN.search(title) is not None


def fetch_greenhouse(company: dict) -> list[dict[str, Any]]:
    token = company["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except requests.RequestException:
        return []

    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title", "")
        track = company["track"]
        if track == "both":
            track = "python" if "python" in title.lower() else "sql_dba"
        if not _is_relevant_title(title, track):
            continue
        loc = item.get("location", {}) or {}
        jobs.append(
            {
                "company": company["name"],
                "title": title,
                "location": loc.get("name", "") if isinstance(loc, dict) else str(loc),
                "track": track,
                "source": "greenhouse",
                "job_url": item.get("absolute_url", ""),
                "description": item.get("content", "") or "",
                "posted_at": item.get("updated_at") or item.get("first_published"),
            }
        )
    return jobs


def fetch_lever(company: dict) -> list[dict[str, Any]]:
    token = company["token"]
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except requests.RequestException:
        return []

    if not isinstance(data, list):
        return []

    jobs = []
    for item in data:
        title = item.get("text", "")
        track = company["track"]
        if track == "both":
            track = "python" if "python" in title.lower() else "sql_dba"
        if not _is_relevant_title(title, track):
            continue
        cats = item.get("categories", {}) or {}
        jobs.append(
            {
                "company": company["name"],
                "title": title,
                "location": cats.get("location", ""),
                "track": track,
                "source": "lever",
                "job_url": item.get("hostedUrl", ""),
                "description": item.get("descriptionPlain", "") or "",
                "posted_at": _parse_date(item.get("createdAt")),
            }
        )
    return jobs


def fetch_ashby(company: dict) -> list[dict[str, Any]]:
    token = company["token"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except requests.RequestException:
        return []

    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title", "")
        track = company["track"]
        if track == "both":
            track = "python" if "python" in title.lower() else "sql_dba"
        if not _is_relevant_title(title, track):
            continue
        jobs.append(
            {
                "company": company["name"],
                "title": title,
                "location": item.get("location", ""),
                "track": track,
                "source": "ashby",
                "job_url": item.get("jobUrl", ""),
                "description": item.get("descriptionPlain", "") or "",
                "posted_at": item.get("publishedAt"),
            }
        )
    return jobs


def fetch_company_jobs(company: dict) -> list[dict[str, Any]]:
    ats = company.get("ats", "").lower()
    if ats == "greenhouse":
        return fetch_greenhouse(company)
    if ats == "lever":
        return fetch_lever(company)
    if ats == "ashby":
        return fetch_ashby(company)
    return []


def fetch_all_companies(companies: list[dict]) -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    for company in companies:
        try:
            jobs = fetch_company_jobs(company)
            all_jobs.extend(jobs)
        except Exception as exc:
            print(f"  [warn] {company['name']}: {exc}")
    return all_jobs
