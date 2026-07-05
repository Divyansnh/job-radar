"""LinkedIn People search hints when no trusted email is available."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus


@dataclass
class LinkedInSearch:
    label: str
    keywords: str
    url: str
    why: str


@dataclass
class LinkedInHints:
    company: str
    title: str
    track: str
    searches: list[LinkedInSearch] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "title": self.title,
            "track": self.track,
            "searches": [
                {"label": s.label, "keywords": s.keywords, "url": s.url, "why": s.why}
                for s in self.searches
            ],
            "steps": self.steps,
        }


def _people_url(keywords: str) -> str:
    return (
        "https://www.linkedin.com/search/results/people/"
        f"?keywords={quote_plus(keywords)}&origin=GLOBAL_SEARCH_HEADER"
    )


def build_linkedin_hints(job: dict[str, Any]) -> LinkedInHints:
    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    track = job.get("track") or "python"

    if track == "sql_dba":
        role_terms = ("database", "DBA", "PostgreSQL", "data engineer")
        manager_terms = ("engineering manager database", "head of data", "data platform")
    else:
        role_terms = ("python", "backend", "software engineer", "API")
        manager_terms = ("engineering manager", "backend lead", "head of engineering")

    searches: list[LinkedInSearch] = [
        LinkedInSearch(
            "Recruiter / talent",
            f"{company} recruiter",
            _people_url(f"{company} recruiter"),
            "Usually owns scheduling and can route you to the hiring team.",
        ),
        LinkedInSearch(
            "Technical recruiter",
            f"{company} technical recruiter",
            _people_url(f"{company} technical recruiter"),
            "Better for engineering roles than generic HR.",
        ),
        LinkedInSearch(
            "Hiring manager (role)",
            f"{company} {title}",
            _people_url(f"{company} {title}"),
            "People with a similar title may be on the interview panel.",
        ),
    ]

    for term in manager_terms[:2]:
        searches.append(
            LinkedInSearch(
                "Engineering leadership",
                f"{company} {term}",
                _people_url(f"{company} {term}"),
                "Small teams: the EM or lead often reads inbound mail directly.",
            )
        )

    for term in role_terms[:2]:
        searches.append(
            LinkedInSearch(
                "Peer engineers",
                f"{company} {term}",
                _people_url(f"{company} {term}"),
                "Peers sometimes forward strong candidates to the hiring manager.",
            )
        )

    steps = [
        f"Open the company on LinkedIn → People tab, or use a search link below.",
        "Pick 1–2 people (recruiter + hiring manager). Avoid messaging five at once.",
        "On the job page here, paste: Name | email@company.com | LinkedIn URL (one per line).",
        "Use Hunter or the profile contact info if email is not public — then click Send to contacts.",
    ]

    return LinkedInHints(company=company, title=title, track=track, searches=searches[:6], steps=steps)
