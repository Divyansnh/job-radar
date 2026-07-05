"""Find recruiter / careers emails for outreach."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import requests

_JUNK_EMAIL_DOMAINS = ("example.com", "sentry.io", "wixpress.com", "linkedin.com")
_ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "job-boards.",
)
_PORTAL_HOSTS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "naukri.com",
    "google.com",
)
_PREFERRED_LOCAL = ("careers", "jobs", "hr", "hiring", "talent", "recruiting", "recruitment")
_HR_DEPARTMENTS = ("hr", "recruiting", "talent", "human_resources", "people", "support")
_TRUSTED_SOURCES = frozenset({"stored", "description", "hunter", "manual"})


def is_trusted_source(source: str) -> bool:
    """Emails from these sources are safe for automatic outreach."""
    return source in _TRUSTED_SOURCES


def emails_in_text(text: str) -> list[str]:
    if not text:
        return []
    found = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    clean: list[str] = []
    for email in found:
        lower = email.lower()
        if any(junk in lower for junk in _JUNK_EMAIL_DOMAINS):
            continue
        if email not in clean:
            clean.append(email)
    return clean


def domain_from_job_url(job_url: str | None) -> str | None:
    if not job_url:
        return None
    host = urlparse(job_url).netloc.lower().removeprefix("www.")
    if not host:
        return None
    if any(portal in host for portal in _PORTAL_HOSTS):
        return None
    if any(ats in host for ats in _ATS_HOSTS):
        return None
    return host


def guess_contact_email(company: str, description: str = "") -> str | None:
    """Legacy fallback: JD scan then careers@company guess."""
    for email in emails_in_text(description):
        return email

    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    if not slug:
        return None
    return f"careers@{slug}.com"


def _pick_hunter_email(emails: list[dict[str, Any]]) -> str | None:
    if not emails:
        return None
    ranked: list[tuple[int, str]] = []
    for entry in emails:
        value = entry.get("value") or ""
        if not value:
            continue
        score = int(entry.get("confidence") or 0)
        lower = value.lower()
        if entry.get("type") == "generic":
            score += 20
        if any(part in lower for part in _PREFERRED_LOCAL):
            score += 30
        dept = (entry.get("department") or "").lower()
        if dept in _HR_DEPARTMENTS:
            score += 15
        ranked.append((score, value))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def hunter_domain_search(
    *,
    domain: str | None = None,
    company: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """Query Hunter.io Domain Search. Uses 1 credit when results are returned."""
    key = api_key or os.getenv("HUNTER_API_KEY")
    if not key:
        return None
    if not domain and not company:
        return None

    params: dict[str, str] = {"api_key": key, "limit": "10", "type": "generic"}
    if domain:
        params["domain"] = domain
    else:
        params["company"] = company

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        emails = data.get("emails") or []
        picked = _pick_hunter_email(emails)
        if picked:
            return picked
        # Fall back to any email if no generic match
        return _pick_hunter_email([e for e in emails if e.get("value")])
    except (requests.RequestException, ValueError) as exc:
        print(f"  [hunter] lookup failed: {exc}")
        return None


def find_contact_email(
    company: str,
    description: str = "",
    job_url: str | None = None,
    *,
    use_hunter: bool | None = None,
    allow_guess: bool = False,
) -> tuple[str | None, str]:
    """
    Resolve best contact email and return (email, source).
    source: stored | description | hunter | manual | guess | none

    By default allow_guess=False — guessed careers@slug.com addresses are not
  returned; use LinkedIn hints + manual contacts instead.
    """
    for email in emails_in_text(description):
        return email, "description"

    if use_hunter is None:
        use_hunter = bool(os.getenv("HUNTER_API_KEY"))

    if use_hunter:
        domain = domain_from_job_url(job_url)
        hunter_email = hunter_domain_search(domain=domain, company=company if not domain else None)
        if hunter_email:
            return hunter_email, "hunter"
        if not domain:
            hunter_email = hunter_domain_search(company=company)
            if hunter_email:
                return hunter_email, "hunter"

    if not allow_guess:
        return None, "none"

    guessed = guess_contact_email(company, "")
    if guessed:
        return guessed, "guess"
    return None, "none"


_RECRUITER_LOCALS = (
    "careers",
    "jobs",
    "hr",
    "hiring",
    "talent",
    "people",
    "recruitment",
    "recruit",
    "apply",
    "job",
    "humanresources",
    "career",
    "staffing",
)


def classify_audience(email: str | None) -> str:
    """
    decision_maker: founders, CTOs, EMs, named people in the JD.
    recruiter: careers@, hr@, talent@, and other generic inboxes.
    """
    if not email:
        return "recruiter"
    lower = email.lower().strip()
    local = lower.split("@", 1)[0] if "@" in lower else lower
    if local in _RECRUITER_LOCALS:
        return "recruiter"
    if any(token in local for token in ("recruit", "talent", "staffing")):
        return "recruiter"
    return "decision_maker"
