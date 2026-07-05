"""Outreach engine — JD signals, email composition, confidence scoring."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from job_radar.email_finder import classify_audience

_BANNED_PHRASES = (
    "i hope this finds you well",
    "i came across your profile",
    "exciting opportunity",
    "passionate about",
    "would love to connect",
    "worth a 10-minute chat",
    "teams hiring for this usually need",
    "just checking in",
    "saw you are hiring",
    "saw you're hiring",
    "usually means",
    "reads like a team under",
    "either become useful fast or become expensive",
)

_DBA_KEYWORDS = (
    "postgresql", "postgres", "sql server", "migration", "etl", "backup", "restore",
    "indexing", "replication", "dba", "aurora", "pl/sql", "t-sql",
)
_PYTHON_KEYWORDS = (
    "fastapi", "django", "flask", "python", "rest api", "backend", "postgresql",
    "microservices", "aws", "api", "etl",
)

_ENTERPRISE_HINTS = (
    "infosys", "amazon", "tcs", "wipro", "accenture", "microsoft", "google",
    "ibm", "oracle", "cognizant", "capgemini", "deloitte", "pwc", "hsbc",
)
_STARTUP_HINTS = ("startup", "seed", "stealth", "yc ", "y combinator")


@dataclass
class OutreachSignals:
    level: int
    company: str
    title: str
    track: str
    hook: str
    hook_short: str
    stack_label: str
    stack_tokens: list[str] = field(default_factory=list)
    jd_themes: list[str] = field(default_factory=list)
    archetype: str = "growth_saas"
    audience: str = "decision_maker"


@dataclass
class ConfidenceReport:
    score: int
    signals_used: list[str]
    signals_missing: list[str]
    fact_ratio: float

    def format_summary(self) -> str:
        used = "\n".join(f"  + {s}" for s in self.signals_used)
        missing = "\n".join(f"  - {s}" for s in self.signals_missing)
        return (
            f"Personalization: {self.score}% ({int(self.fact_ratio * 100)}% fact-based)\n"
            f"Signals used:\n{used}\nMissing:\n{missing}"
        )


@dataclass
class ComposedEmail:
    subject: str
    body: str
    persona: str
    structure: list[str]
    archetype: str
    confidence: ConfidenceReport
    opener_type: str

    def meta_json(self) -> str:
        return json.dumps(
            {
                "persona": self.persona,
                "structure": self.structure,
                "archetype": self.archetype,
                "confidence_score": self.confidence.score,
                "opener_type": self.opener_type,
                "subject": self.subject,
                "signals_used": self.confidence.signals_used,
            }
        )


def _clean_jd(description: str) -> str:
    text = re.sub(r"<[^>]+>", " ", description or "")
    return re.sub(r"\s+", " ", text).strip()


def _pick_keywords(text: str, track: str) -> list[str]:
    kws = _DBA_KEYWORDS if track == "sql_dba" else _PYTHON_KEYWORDS
    return [kw for kw in kws if kw in text.lower()]


def _sentence_with_keyword(text: str, keyword: str, max_len: int = 110) -> str | None:
    for sent in re.split(r"[.!?\n]+", text):
        s = sent.strip()
        if keyword in s.lower() and 12 < len(s) <= max_len:
            return s
    return None


def jd_hook(description: str, track: str) -> str:
    text = _clean_jd(description)
    if not text:
        return "backend services" if track == "python" else "database operations"
    kws = _DBA_KEYWORDS if track == "sql_dba" else _PYTHON_KEYWORDS
    for kw in kws:
        if kw in text.lower():
            sent = _sentence_with_keyword(text, kw)
            return sent if sent else kw
    preview = text[:90].rstrip()
    return preview + ("..." if len(text) > 90 else "")


def _hook_short(hook: str, max_len: int = 55) -> str:
    h = hook.strip().rstrip(".")
    for prefix in ("Own ", "own ", "Build ", "build ", "Manage ", "manage "):
        if h.startswith(prefix):
            h = h[len(prefix) :]
    if len(h) <= max_len:
        return h[0].lower() + h[1:] if len(h) > 1 else h
    cut = h[:max_len].rsplit(" ", 1)[0]
    return cut[0].lower() + cut[1:] if cut else "your stack"


def _stack_label(tokens: list[str], track: str) -> str:
    if not tokens:
        return "PostgreSQL" if track == "sql_dba" else "Python"
    primary = tokens[0]
    if primary in ("fastapi", "django", "flask"):
        return primary.title()
    if primary in ("postgresql", "postgres"):
        return "PostgreSQL"
    if primary == "etl":
        return "ETL"
    return primary.title()


def _jd_themes(text: str, track: str) -> list[str]:
    """Factual themes visible in the JD — no inference."""
    lower = text.lower()
    themes: list[str] = []
    mapping = (
        [("backup", "backups"), ("restore", "restore"), ("etl", "ETL"),
         ("replication", "replication"), ("migration", "migrations"),
         ("24/7", "24/7 support"), ("on-call", "on-call"), ("postgresql", "PostgreSQL"),
         ("sql server", "SQL Server"), ("index", "indexing")]
        if track == "sql_dba"
        else [
            ("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask"),
            ("postgresql", "PostgreSQL"), ("microservices", "microservices"),
            ("aws", "AWS"), ("api", "APIs"), ("etl", "ETL"),
        ]
    )
    for needle, label in mapping:
        if needle in lower and label not in themes:
            themes.append(label)
    return themes[:5]


def detect_company_archetype(job: dict[str, Any]) -> str:
    if job.get("company_archetype"):
        return job["company_archetype"]
    company = (job.get("company") or "").lower()
    text = _clean_jd(job.get("description", "")).lower()
    combined = f"{company} {text}"
    if any(h in combined for h in _ENTERPRISE_HINTS):
        return "enterprise"
    if any(h in combined for h in ("series a", "series b", "series-a", "series-b")):
        return "series_a"
    if any(h in combined for h in _STARTUP_HINTS):
        return "startup_small"
    if any(w in combined for w in ("global", "enterprise", "multinational", "acceleration center")):
        return "enterprise"
    if len(company) < 18 and company.count(" ") <= 1:
        return "startup_small"
    return "growth_saas"


def extract_signals(job: dict[str, Any], config: dict | None = None) -> OutreachSignals:
    cfg = (config or {}).get("outreach", {})
    level = max(0, min(3, int(cfg.get("personalization_level", 1))))
    desc = job.get("description", "") or ""
    text = _clean_jd(desc)
    track = job.get("track", "python")
    tokens = _pick_keywords(text, track)
    hook = jd_hook(desc, track)
    audience = job.get("outreach_audience") or classify_audience(job.get("contact_email"))
    return OutreachSignals(
        level=level,
        company=job.get("company", "your company"),
        title=job.get("title", "the role"),
        track=track,
        hook=hook,
        hook_short=_hook_short(hook),
        stack_label=_stack_label(tokens, track),
        stack_tokens=tokens,
        jd_themes=_jd_themes(text, track),
        archetype=detect_company_archetype(job),
        audience=audience,
    )


def compute_confidence(signals: OutreachSignals, job: dict[str, Any]) -> ConfidenceReport:
    used: list[str] = []
    missing: list[str] = ["Recent company news", "Engineering blog", "GitHub activity", "Funding stage"]
    score = 25
    facts = 0
    total_blocks = 4

    if job.get("description"):
        used.append("Job description")
        score += 25
        facts += 1
    if signals.stack_tokens:
        used.append("Tech stack from JD")
        score += 15
        facts += 1
    if signals.jd_themes:
        used.append(f"JD themes ({', '.join(signals.jd_themes[:3])})")
        score += 10
        facts += 1
    if job.get("contact_email"):
        used.append("Named contact" if signals.audience == "decision_maker" else "Recruiter inbox")
        score += 5
    if signals.level >= 2:
        score += 10
        facts += 1
    if job.get("company"):
        used.append("Company name")
        score += 5

    score = min(95, score)
    if signals.level >= 3:
        missing = [m for m in missing if m != "Funding stage"]

    return ConfidenceReport(
        score=score,
        signals_used=used,
        signals_missing=missing,
        fact_ratio=round(facts / total_blocks, 2),
    )


def _themes_phrase(themes: list[str]) -> str:
    if not themes:
        return "the technical requirements"
    if len(themes) == 1:
        return themes[0]
    if len(themes) == 2:
        return f"{themes[0]} and {themes[1]}"
    return ", ".join(themes[:-1]) + f", and {themes[-1]}"


_EXPIRY_TRACKER_REPO = "https://github.com/Divyansnh/expiry_tracker_final"
_EXPIRY_TRACKER_DEMO = "https://www.youtube.com/watch?v=Dge_LY-7zbg"


def _opening_line(signals: OutreachSignals, job: dict[str, Any]) -> str:
    tech = _themes_phrase(signals.jd_themes) if signals.jd_themes else signals.stack_label
    role = f"{signals.title} role at {signals.company}"
    base = f"Your {role} focuses on {tech} — I have built with that stack."
    if job.get("status") == "applied" and job.get("applied_at"):
        try:
            raw = job["applied_at"].replace("Z", "+00:00")
            date_str = datetime.fromisoformat(raw).strftime("%d %b")
        except ValueError:
            date_str = str(job["applied_at"])[:10]
        return f"I applied on {date_str}. {base}"
    return base


def _python_project_story(signals: OutreachSignals) -> str:
    tech = _themes_phrase(signals.jd_themes) if signals.jd_themes else "Python backend work"
    return (
        "I built an AI-powered Expiry Tracker to fix manual expiry-date tracking — "
        "product waste and operational inefficiency. "
        "Using Python, Flask, PostgreSQL, Azure Computer Vision OCR, Zoho integration, and APScheduler, "
        "I developed a system that extracts expiry dates from images, tracks inventory, "
        "sends proactive alerts, and generates reports. "
        f"It strengthened my REST APIs, database design, third-party API integration, and backend automation — "
        f"the practical Python work your {tech} posting calls for."
    )


def _dba_project_story() -> str:
    return (
        "At Thomson Reuters I worked on production database problems. "
        "Legacy account data had to reach Aurora PostgreSQL inside a private VPC without exposing RDS. "
        "I built Informatica + stored-procedure ETL, Lambda-in-VPC with Secrets Manager for secure access, "
        "and a bulk upsert that processed 5,000 contact updates in 1.32 minutes."
    )


def _project_story(signals: OutreachSignals) -> str:
    return _dba_project_story() if signals.track == "sql_dba" else _python_project_story(signals)


def _project_github(profile: dict[str, str]) -> str:
    return (
        profile.get("PROJECT_GITHUB_URL")
        or _EXPIRY_TRACKER_REPO
    ).strip()


def _demo_url(profile: dict[str, str]) -> str:
    return (profile.get("DEMO_VIDEO_URL") or _EXPIRY_TRACKER_DEMO).strip()


def _python_links_block(profile: dict[str, str]) -> str:
    github = _project_github(profile)
    demo = _demo_url(profile)
    lines = [f"GitHub: {github}"]
    if demo:
        lines.append(f"Demo: {demo}")
    return "\n".join(lines)


def _your_email(profile: dict[str, str]) -> str:
    return (profile.get("YOUR_EMAIL") or profile.get("SMTP_USER") or "").strip()


def _resume_line() -> str:
    return "My resume is attached for your review."


def _simple_cta() -> str:
    return "I would welcome a conversation if this aligns with what you are looking for."


def _sign_off(name: str, profile: dict[str, str]) -> str:
    text = f"Kind regards,\n\n{name}"
    email = _your_email(profile)
    if email:
        text += f"\n{email}"
    return text


def _email_footer(profile: dict[str, str], signals: OutreachSignals, name: str) -> str:
    parts: list[str] = []
    if signals.track == "python":
        parts.append(_python_links_block(profile))
    parts.append(_resume_line())
    parts.append(_sign_off(name, profile))
    return "\n\n".join(parts)


def _greeting(job: dict[str, Any]) -> str:
    name = (job.get("contact_name") or "").strip().split()
    return f"Dear {name[0]}," if name else "Dear Hiring Team,"


def _compose_simple_body(
    job: dict[str, Any],
    profile: dict[str, str],
    signals: OutreachSignals,
    config: dict | None,
) -> str:
    name = profile.get("YOUR_NAME", "")
    parts = [
        _greeting(job),
        _opening_line(signals, job),
        _project_story(signals),
        _simple_cta(),
        _email_footer(profile, signals, name),
    ]
    body = "\n\n".join(parts)
    if profile.get("LINKEDIN_URL"):
        body += f"\n{profile['LINKEDIN_URL']}"
    return body.strip()


def _subject_initial(signals: OutreachSignals) -> str:
    return f"{signals.title} — {signals.company}"[:72]


def _fmt_sent_date(job: dict[str, Any]) -> str:
    raw = job.get("initial_email_sent_at")
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d %b")
    except ValueError:
        return str(raw)[:10]


def _lint(text: str) -> None:
    lower = text.lower()
    for phrase in _BANNED_PHRASES:
        if phrase in lower:
            raise ValueError(f"Banned phrase in outreach copy: {phrase!r}")


def compose_initial(
    job: dict[str, Any],
    profile: dict[str, str],
    config: dict | None = None,
) -> ComposedEmail:
    signals = extract_signals(job, config)
    confidence = compute_confidence(signals, job)
    body = _compose_simple_body(job, profile, signals, config)
    subject = _subject_initial(signals)
    _lint(body)
    audience = signals.audience
    return ComposedEmail(
        subject=subject,
        body=body,
        persona="recruiter" if audience == "recruiter" else "direct",
        structure=["opening", "story", "resume", "cta"],
        archetype=signals.archetype,
        confidence=confidence,
        opener_type="opening",
    )


def _followup_body_python(signals: OutreachSignals, followup_num: int) -> str:
    title = signals.title
    if followup_num == 1:
        return f"""Dear Hiring Team,

I hope you're doing well. I wanted to follow up on my previous email regarding the {title} role.

I remain very interested in the opportunity and would love the chance to discuss how my experience building an AI-powered Expiry Tracker—using Python, Flask, PostgreSQL, Azure OCR, REST APIs, and third-party integrations—could add value to your team.

If you have any questions about my project or background, I'd be happy to answer them.

Thank you for your time, and I look forward to hearing from you."""
    if followup_num == 2:
        return f"""Dear Hiring Team,

I wanted to briefly check in regarding my application for the {title} position.

Since my previous email, I've continued strengthening my Python and backend development skills while refining projects involving API integrations, automation, and database-driven applications. I'm genuinely excited about the opportunity to contribute and continue learning within your engineering team.

If there's any additional information I can provide, I'd be happy to do so.

Thank you again for your consideration."""
    return f"""Dear Hiring Team,

I appreciate how busy hiring can be, so I wanted to send one final follow-up regarding my application.

I'm still very interested in joining your team and believe my experience developing a full-stack Python application with AI, database design, REST APIs, automation, and third-party integrations has prepared me well for a {title} role.

Thank you for considering my application. I hope to have the opportunity to speak with you and learn more about your team."""


def _followup_body_dba(signals: OutreachSignals, followup_num: int) -> str:
    title = signals.title
    if followup_num == 1:
        return f"""Dear Hiring Team,

I hope you're doing well. I wanted to follow up on my previous email regarding the {title} role.

I remain very interested in the opportunity and would love the chance to discuss how my experience at Thomson Reuters—working with PostgreSQL, Aurora, ETL pipelines, stored procedures, and database migration—could add value to your team.

If you have any questions about my background, I'd be happy to answer them.

Thank you for your time, and I look forward to hearing from you."""
    if followup_num == 2:
        return f"""Dear Hiring Team,

I wanted to briefly check in regarding my application for the {title} position.

Since my previous email, I've continued strengthening my database and backend skills while refining work involving ETL workflows, query optimization, and production PostgreSQL operations. I'm genuinely excited about the opportunity to contribute and continue learning within your team.

If there's any additional information I can provide, I'd be happy to do so.

Thank you again for your consideration."""
    return f"""Dear Hiring Team,

I appreciate how busy hiring can be, so I wanted to send one final follow-up regarding my application.

I'm still very interested in joining your team and believe my experience with PostgreSQL migration, Informatica ETL, stored procedures, and secure database architecture at Thomson Reuters has prepared me well for a {title} role.

Thank you for considering my application. I hope to have the opportunity to speak with you and learn more about your team."""


def compose_followup(
    job: dict[str, Any],
    profile: dict[str, str],
    followup_num: int,
    config: dict | None = None,
) -> ComposedEmail:
    signals = extract_signals(job, config)
    confidence = compute_confidence(signals, job)
    name = profile.get("YOUR_NAME", "")
    followup_num = max(1, min(3, int(followup_num)))

    if followup_num == 1:
        subject = f"re: {signals.title} at {signals.company}"[:72]
        opener_type = "followup_recall"
    elif followup_num == 2:
        subject = f"re: {signals.title} — {signals.company}"[:72]
        opener_type = "followup_checkin"
    else:
        subject = f"closing the loop — {signals.company}"[:72]
        opener_type = "followup_close"

    if signals.track == "sql_dba":
        core = _followup_body_dba(signals, followup_num)
    else:
        core = _followup_body_python(signals, followup_num)

    body = f"{core.strip()}\n\n{_email_footer(profile, signals, name)}"

    _lint(body)
    return ComposedEmail(
        subject=subject,
        body=body.strip(),
        persona=job.get("outreach_persona", "direct"),
        structure=[opener_type],
        archetype=signals.archetype,
        confidence=confidence,
        opener_type=opener_type,
    )


# --- Public API ---


def resolve_audience(job: dict[str, Any]) -> str:
    if job.get("outreach_audience") in ("decision_maker", "recruiter"):
        return job["outreach_audience"]
    return classify_audience(job.get("contact_email"))


def should_attach_resume(job: dict[str, Any], config: dict | None = None) -> bool:
    return True


def _with_seed(config: dict | None, salt: int, fn: Callable[..., ComposedEmail], *args: Any) -> ComposedEmail:
    seed = (config or {}).get("outreach", {}).get("seed")
    state = random.getstate()
    if seed is not None:
        random.seed(int(seed) + salt)
    try:
        return fn(*args)
    finally:
        random.setstate(state)


def initial_email(
    job: dict[str, Any], profile: dict[str, str], config: dict | None = None
) -> tuple[str, str]:
    composed = _with_seed(config, 0, compose_initial, job, profile, config)
    return composed.subject, composed.body


def followup_email(
    job: dict[str, Any],
    profile: dict[str, str],
    followup_num: int,
    config: dict | None = None,
) -> tuple[str, str]:
    composed = _with_seed(config, followup_num, compose_followup, job, profile, followup_num, config)
    return composed.subject, composed.body


def compose_with_meta(
    job: dict[str, Any], profile: dict[str, str], config: dict | None = None
) -> ComposedEmail:
    return _with_seed(config, 0, compose_initial, job, profile, config)
