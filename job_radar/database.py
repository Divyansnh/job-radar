"""SQLite tracker for jobs, outreach, and follow-ups."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "tracker.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dedupe_key TEXT UNIQUE NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                track TEXT NOT NULL,
                source TEXT NOT NULL,
                job_url TEXT NOT NULL,
                description TEXT,
                score REAL DEFAULT 0,
                posted_at TEXT,
                discovered_at TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                contact_email TEXT,
                contact_name TEXT,
                outreach_status TEXT DEFAULT 'pending',
                initial_email_sent_at TEXT,
                followup_count INTEGER DEFAULT 0,
                next_followup_at TEXT,
                applied_at TEXT,
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_followup ON jobs(next_followup_at);
            """
        )
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "outreach_meta" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN outreach_meta TEXT")
    if "reply_outcome" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN reply_outcome TEXT DEFAULT 'none'")
    if "contact_source" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN contact_source TEXT")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS job_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            name TEXT,
            email TEXT NOT NULL,
            linkedin_url TEXT,
            outreach_status TEXT DEFAULT 'pending',
            initial_email_sent_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_contacts_job ON job_contacts(job_id);
        """
    )


def job_exists(dedupe_key: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE dedupe_key = ?", (dedupe_key,)
        ).fetchone()
        return row is not None


def insert_job(job: dict[str, Any]) -> int | None:
    if job_exists(job["dedupe_key"]):
        return None
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                dedupe_key, company, title, location, track, source, job_url,
                description, score, posted_at, discovered_at, status, contact_email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?)
            """,
            (
                job["dedupe_key"],
                job["company"],
                job["title"],
                job.get("location", ""),
                job["track"],
                job["source"],
                job["job_url"],
                job.get("description", ""),
                job.get("score", 0),
                job.get("posted_at"),
                now,
                job.get("contact_email"),
            ),
        )
        return cur.lastrowid


def get_todays_queue(limit: int = 10, config: dict | None = None) -> list[dict]:
    fetch_limit = max(limit * 5, 50)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('new', 'queued')
            ORDER BY score DESC, discovered_at ASC
            LIMIT ?
            """,
            (fetch_limit,),
        ).fetchall()
        candidates = [dict(r) for r in rows]

    if config:
        from job_radar.scorer import build_daily_queue

        return build_daily_queue(candidates, config)

    return candidates[:limit]


def mark_applied(job_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'applied', applied_at = ? WHERE id = ?",
            (now, job_id),
        )


def _append_outreach_event(job_id: int, event: dict[str, Any]) -> None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT outreach_meta FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        data: dict[str, Any] = {"events": []}
        if row and row["outreach_meta"]:
            try:
                data = json.loads(row["outreach_meta"])
            except json.JSONDecodeError:
                data = {"events": []}
        if "events" not in data:
            data["events"] = []
        data["events"].append(event)
        conn.execute(
            "UPDATE jobs SET outreach_meta = ? WHERE id = ?",
            (json.dumps(data), job_id),
        )


def mark_email_sent(
    job_id: int,
    followup_days: list[int],
    outreach_meta: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    next_fu = None
    if followup_days:
        next_fu = (datetime.now(timezone.utc) + timedelta(days=followup_days[0])).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE jobs SET
                outreach_status = 'sent',
                initial_email_sent_at = ?,
                next_followup_at = ?,
                followup_count = 0
            WHERE id = ?
            """,
            (now, next_fu, job_id),
        )
    if outreach_meta:
        try:
            event = json.loads(outreach_meta)
        except json.JSONDecodeError:
            event = {"raw": outreach_meta}
        event["kind"] = "initial"
        event["sent_at"] = now
        _append_outreach_event(job_id, event)


def get_due_followups() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE outreach_status IN ('sent', 'followup_1', 'followup_2')
              AND next_followup_at IS NOT NULL
              AND next_followup_at <= ?
              AND followup_count < 3
            """,
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_followup_sent(
    job_id: int,
    followup_count: int,
    followup_days: list[int],
    outreach_meta: str | None = None,
) -> None:
    from datetime import timedelta

    with _connect() as conn:
        row = conn.execute(
            "SELECT initial_email_sent_at FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        initial = row["initial_email_sent_at"] if row else None

    status = f"followup_{followup_count}"
    next_fu = None
    if followup_count < len(followup_days) and initial:
        initial_dt = datetime.fromisoformat(initial)
        days = followup_days[followup_count]
        next_fu = (initial_dt + timedelta(days=days)).isoformat()
    else:
        status = "followup_complete"

    with _connect() as conn:
        conn.execute(
            """
            UPDATE jobs SET
                outreach_status = ?,
                followup_count = ?,
                next_followup_at = ?
            WHERE id = ?
            """,
            (status, followup_count, next_fu, job_id),
        )
    if outreach_meta:
        try:
            event = json.loads(outreach_meta)
        except json.JSONDecodeError:
            event = {"raw": outreach_meta}
        event["kind"] = f"followup_{followup_count}"
        event["sent_at"] = datetime.now(timezone.utc).isoformat()
        _append_outreach_event(job_id, event)


_REPLY_OUTCOMES = frozenset({"none", "replied", "interview", "offer"})


def set_reply_outcome(job_id: int, outcome: str) -> bool:
    if outcome not in _REPLY_OUTCOMES:
        return False
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE jobs SET reply_outcome = ? WHERE id = ?",
            (outcome, job_id),
        )
        return cur.rowcount > 0


def outreach_learning_stats() -> dict[str, Any]:
    """Aggregate reply rates by persona, archetype, and opener for sent emails."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT outreach_meta, reply_outcome, company, track
            FROM jobs
            WHERE initial_email_sent_at IS NOT NULL AND outreach_meta IS NOT NULL
            """
        ).fetchall()

    by_persona: dict[str, dict[str, int]] = {}
    by_archetype: dict[str, dict[str, int]] = {}
    by_opener: dict[str, dict[str, int]] = {}

    def _bump(bucket: dict[str, dict[str, int]], key: str, replied: bool) -> None:
        if key not in bucket:
            bucket[key] = {"sent": 0, "replied": 0}
        bucket[key]["sent"] += 1
        if replied:
            bucket[key]["replied"] += 1

    for row in rows:
        replied = row["reply_outcome"] in ("replied", "interview", "offer")
        try:
            data = json.loads(row["outreach_meta"] or "{}")
        except json.JSONDecodeError:
            continue
        for ev in data.get("events", []):
            if ev.get("kind") != "initial":
                continue
            _bump(by_persona, ev.get("persona", "unknown"), replied)
            _bump(by_archetype, ev.get("archetype", "unknown"), replied)
            _bump(by_opener, ev.get("opener_type", "unknown"), replied)

    def _rates(bucket: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
        out = []
        for key, counts in sorted(bucket.items()):
            sent = counts["sent"]
            rep = counts["replied"]
            out.append({
                "key": key,
                "sent": sent,
                "replied": rep,
                "rate_pct": round(100 * rep / sent, 1) if sent else 0.0,
            })
        return out

    return {
        "by_persona": _rates(by_persona),
        "by_archetype": _rates(by_archetype),
        "by_opener": _rates(by_opener),
        "total_sent": sum(c["sent"] for c in by_persona.values()),
    }


def stats() -> dict[str, int]:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        applied = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'applied'"
        ).fetchone()[0]
        emailed = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE initial_email_sent_at IS NOT NULL"
        ).fetchone()[0]
        return {"total": total, "applied": applied, "emailed": emailed}


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def get_job(job_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_jobs(
    *,
    status: str | None = None,
    outreach_status: str | None = None,
    track: str | None = None,
    search: str | None = None,
    emailed_only: bool = False,
    pending_outreach: bool = False,
    order_by: str = "score_desc",
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if outreach_status:
        clauses.append("outreach_status = ?")
        params.append(outreach_status)
    if track:
        clauses.append("track = ?")
        params.append(track)
    if emailed_only:
        clauses.append("initial_email_sent_at IS NOT NULL")
    if pending_outreach:
        clauses.append("outreach_status = 'pending'")
    if search:
        clauses.append("(company LIKE ? OR title LIKE ? OR location LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_map = {
        "score_desc": "score DESC, discovered_at ASC",
        "score_asc": "score ASC, discovered_at DESC",
        "discovered_desc": "discovered_at DESC",
        "applied_desc": "applied_at DESC",
        "company_asc": "company ASC, title ASC",
    }
    order_sql = order_map.get(order_by, order_map["score_desc"])

    sql = f"""
        SELECT * FROM jobs
        {where}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def count_jobs(
    *,
    status: str | None = None,
    outreach_status: str | None = None,
    track: str | None = None,
    search: str | None = None,
    emailed_only: bool = False,
    pending_outreach: bool = False,
) -> int:
    clauses: list[str] = []
    params: list[Any] = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if outreach_status:
        clauses.append("outreach_status = ?")
        params.append(outreach_status)
    if track:
        clauses.append("track = ?")
        params.append(track)
    if emailed_only:
        clauses.append("initial_email_sent_at IS NOT NULL")
    if pending_outreach:
        clauses.append("outreach_status = 'pending'")
    if search:
        clauses.append("(company LIKE ? OR title LIKE ? OR location LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT COUNT(*) FROM jobs {where}"

    with _connect() as conn:
        return conn.execute(sql, params).fetchone()[0]


def list_applied_jobs(limit: int = 200) -> list[dict[str, Any]]:
    return list_jobs(status="applied", order_by="applied_desc", limit=limit)


def update_notes(job_id: int, notes: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE jobs SET notes = ? WHERE id = ?",
            (notes.strip() or None, job_id),
        )
        return cur.rowcount > 0


def update_contact_email(job_id: int, email: str, source: str = "manual") -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE jobs SET contact_email = ?, contact_source = ?
            WHERE id = ?
            """,
            (email.strip(), source, job_id),
        )
        return cur.rowcount > 0


def set_outreach_status(job_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET outreach_status = ? WHERE id = ?",
            (status, job_id),
        )


def add_job_contacts(job_id: int, contacts: list[dict[str, str]]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    with _connect() as conn:
        for c in contacts:
            email = (c.get("email") or "").strip().lower()
            if not email:
                continue
            exists = conn.execute(
                "SELECT 1 FROM job_contacts WHERE job_id = ? AND email = ?",
                (job_id, email),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO job_contacts (job_id, name, email, linkedin_url, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    (c.get("name") or "").strip() or None,
                    email,
                    (c.get("linkedin_url") or "").strip() or None,
                    now,
                ),
            )
            added += 1
    return added


def list_job_contacts(job_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM job_contacts
            WHERE job_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_job_contact(contact_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM job_contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        return dict(row) if row else None


def mark_contact_email_sent(contact_id: int, outreach_meta: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT job_id FROM job_contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not row:
            return
        job_id = row["job_id"]
        conn.execute(
            """
            UPDATE job_contacts SET
                outreach_status = 'sent',
                initial_email_sent_at = ?
            WHERE id = ?
            """,
            (now, contact_id),
        )
        conn.execute(
            """
            UPDATE jobs SET
                outreach_status = 'sent',
                contact_email = (SELECT email FROM job_contacts WHERE id = ?),
                contact_source = 'manual',
                initial_email_sent_at = COALESCE(initial_email_sent_at, ?)
            WHERE id = ?
            """,
            (contact_id, now, job_id),
        )
    if outreach_meta:
        try:
            event = json.loads(outreach_meta)
        except json.JSONDecodeError:
            event = {"raw": outreach_meta}
        event["kind"] = "initial_manual"
        event["contact_id"] = contact_id
        event["sent_at"] = now
        _append_outreach_event(job_id, event)


def count_needs_contacts() -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE outreach_status = 'needs_contacts'"
        ).fetchone()[0]


def dashboard_stats() -> dict[str, int]:
    base = stats()
    with _connect() as conn:
        queued = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('new', 'queued')"
        ).fetchone()[0]
        pending_outreach = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE outreach_status = 'pending'"
        ).fetchone()[0]
        needs_contacts = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE outreach_status = 'needs_contacts'"
        ).fetchone()[0]
        followups_due = conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE outreach_status IN ('sent', 'followup_1', 'followup_2')
              AND next_followup_at IS NOT NULL
              AND next_followup_at <= ?
              AND followup_count < 3
            """,
            (datetime.now(timezone.utc).isoformat(),),
        ).fetchone()[0]
        sql_dba = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE track = 'sql_dba'"
        ).fetchone()[0]
        python_track = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE track = 'python'"
        ).fetchone()[0]
    return {
        **base,
        "queued": queued,
        "pending_outreach": pending_outreach,
        "needs_contacts": needs_contacts,
        "followups_due": followups_due,
        "sql_dba": sql_dba,
        "python": python_track,
    }


def _local_day_start_utc(day: date) -> str:
    local = datetime.combine(day, datetime.min.time()).astimezone()
    return local.astimezone(timezone.utc).isoformat()


def _local_day_end_utc(day: date) -> str:
    local = datetime.combine(day, datetime.max.time()).astimezone()
    return local.astimezone(timezone.utc).isoformat()


def count_applied_on_date(day: date) -> int:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status = 'applied'
              AND applied_at >= ? AND applied_at <= ?
            """,
            (_local_day_start_utc(day), _local_day_end_utc(day)),
        ).fetchone()[0]


def count_applied_since(start: date) -> int:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status = 'applied' AND applied_at >= ?
            """,
            (_local_day_start_utc(start),),
        ).fetchone()[0]


def count_emailed_since(start: date) -> int:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE initial_email_sent_at IS NOT NULL
              AND initial_email_sent_at >= ?
            """,
            (_local_day_start_utc(start),),
        ).fetchone()[0]


def count_followups_completed() -> int:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE outreach_status IN ('followup_complete', 'followup_2')
              AND followup_count > 0
            """
        ).fetchone()[0]


def applications_per_day(days: int = 14) -> list[dict[str, Any]]:
    today = date.today()
    start = today - timedelta(days=days - 1)
    series: list[dict[str, Any]] = []
    for i in range(days):
        d = start + timedelta(days=i)
        series.append({"date": d.strftime("%d %b"), "count": count_applied_on_date(d)})
    return series


def pipeline_funnel() -> dict[str, int]:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        queued = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('new', 'queued')"
        ).fetchone()[0]
        applied = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'applied'"
        ).fetchone()[0]
        emailed = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE initial_email_sent_at IS NOT NULL"
        ).fetchone()[0]
        followup_done = conn.execute(
            """
            SELECT COUNT(*) FROM jobs WHERE outreach_status = 'followup_complete'
            """
        ).fetchone()[0]
    return {
        "tracked": total,
        "queued": queued,
        "applied": applied,
        "emailed": emailed,
        "followup_complete": followup_done,
    }


def track_activity_breakdown() -> dict[str, dict[str, int]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT track, status, COUNT(*) AS n
            FROM jobs
            GROUP BY track, status
            """
        ).fetchall()
    result: dict[str, dict[str, int]] = {
        "sql_dba": {"queued": 0, "applied": 0},
        "python": {"queued": 0, "applied": 0},
    }
    for row in rows:
        track = row["track"]
        if track not in result:
            result[track] = {"queued": 0, "applied": 0}
        if row["status"] == "applied":
            result[track]["applied"] = row["n"]
        elif row["status"] in ("new", "queued"):
            result[track]["queued"] = result[track].get("queued", 0) + row["n"]
    return result
