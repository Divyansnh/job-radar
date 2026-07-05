"""Flask dashboard for Job Radar."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

from job_radar import database
from job_radar.daily import load_config

_PKG = Path(__file__).resolve().parent.parent


def _filter_jobs(
    jobs: list[dict],
    *,
    search: str | None = None,
    track: str | None = None,
    outreach: str | None = None,
) -> list[dict]:
    result = jobs
    if track:
        result = [j for j in result if j.get("track") == track]
    if outreach == "pending":
        result = [j for j in result if j.get("outreach_status") == "pending"]
    elif outreach == "sent":
        result = [
            j for j in result
            if j.get("initial_email_sent_at")
            and j.get("outreach_status") != "followup_complete"
        ]
    elif outreach == "complete":
        result = [j for j in result if j.get("outreach_status") == "followup_complete"]
    if search:
        q = search.lower()
        result = [
            j for j in result
            if q in (j.get("company") or "").lower()
            or q in (j.get("title") or "").lower()
            or q in (j.get("location") or "").lower()
        ]
    return result


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_PKG / "templates"),
        static_folder=str(_PKG / "static"),
    )
    app.config["SECRET_KEY"] = "job-radar-local"

    @app.context_processor
    def inject_globals():
        return {
            "now": datetime.now(),
            "nav_stats": database.dashboard_stats(),
        }

    @app.template_filter("fmt_date")
    def fmt_date(value: str | None) -> str:
        if not value:
            return "—"
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d %b %Y")
        except ValueError:
            return value[:10] if len(value) >= 10 else value

    @app.template_filter("days_ago")
    def days_ago(value: str | None) -> str:
        if not value:
            return "—"
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            delta = datetime.now(dt.tzinfo or timezone.utc) - dt
            days = delta.days
            if days == 0:
                return "Today"
            if days == 1:
                return "1 day ago"
            return f"{days} days ago"
        except ValueError:
            return "—"

    @app.get("/")
    def dashboard():
        config = load_config()
        from job_radar.analytics import build_activity_report

        report = build_activity_report(config)
        return render_template(
            "dashboard.html",
            page_title="Dashboard",
            active_nav="dashboard",
            report=report,
        )

    @app.get("/applied")
    def applied_page():
        track = request.args.get("track") or None
        outreach = request.args.get("outreach") or None
        search = request.args.get("q") or None
        order = request.args.get("sort") or "applied_desc"
        all_applied = database.list_applied_jobs(limit=500)
        jobs = _filter_jobs(all_applied, search=search, track=track, outreach=outreach)
        if order == "score_desc":
            jobs.sort(key=lambda j: j.get("score") or 0, reverse=True)
        elif order == "company_asc":
            jobs.sort(key=lambda j: (j.get("company") or "", j.get("title") or ""))

        emailed = sum(1 for j in all_applied if j.get("initial_email_sent_at"))
        no_email = len(all_applied) - emailed
        dba = sum(1 for j in all_applied if j.get("track") == "sql_dba")
        py = sum(1 for j in all_applied if j.get("track") == "python")
        with_notes = sum(1 for j in all_applied if j.get("notes"))
        avg_score = (
            round(sum(j.get("score", 0) for j in all_applied) / len(all_applied), 1)
            if all_applied else 0.0
        )
        page_stats = {
            "total": len(all_applied),
            "emailed": emailed,
            "no_email": no_email,
            "sql_dba": dba,
            "python": py,
            "with_notes": with_notes,
            "avg_score": avg_score,
            "showing": len(jobs),
        }
        return render_template(
            "applied.html",
            page_title="Applied",
            active_nav="applied",
            jobs=jobs,
            page_stats=page_stats,
            filters={"track": track, "outreach": outreach, "q": search, "sort": order},
        )

    @app.get("/outreach")
    def outreach_page():
        config = load_config()
        view = request.args.get("view") or None
        search = request.args.get("q") or None
        track = request.args.get("track") or None

        due = database.get_due_followups()
        pending = database.list_jobs(pending_outreach=True, order_by="score_desc", limit=500)
        sent = database.list_jobs(emailed_only=True, order_by="discovered_desc", limit=500)
        complete = database.list_jobs(outreach_status="followup_complete", limit=500)
        needs_contacts = database.list_jobs(outreach_status="needs_contacts", limit=500)
        applied_gap = [
            j for j in database.list_applied_jobs(limit=500)
            if not j.get("initial_email_sent_at")
        ]

        if not view:
            view = "due" if due else ("needs_contacts" if needs_contacts else "pending")

        view_jobs = {
            "due": due,
            "pending": pending,
            "sent": sent,
            "complete": complete,
            "applied_gap": applied_gap,
            "needs_contacts": needs_contacts,
        }.get(view, pending)
        jobs = _filter_jobs(view_jobs, search=search, track=track)

        applied_total = database.count_jobs(status="applied")
        coverage = round((len(sent) / applied_total) * 100, 1) if applied_total else 0.0
        page_stats = {
            "due": len(due),
            "pending": len(pending),
            "sent": len(sent),
            "complete": len(complete),
            "applied_gap": len(applied_gap),
            "needs_contacts": len(needs_contacts),
            "coverage": coverage,
            "showing": len(jobs),
        }
        return render_template(
            "outreach.html",
            page_title="Outreach",
            active_nav="outreach",
            jobs=jobs,
            page_stats=page_stats,
            view=view,
            followup_days=config.get("followup_days", [3, 7, 12]),
            filters={"q": search, "track": track},
        )

    @app.get("/jobs")
    def jobs_page():
        config = load_config()
        status = request.args.get("status") or None
        track = request.args.get("track") or None
        search = request.args.get("q") or None
        order = request.args.get("sort") or "score_desc"
        jobs = database.list_jobs(
            status=status,
            track=track,
            search=search,
            order_by=order,
            limit=500,
        )
        total = database.count_jobs(status=status, track=track, search=search)
        stats = database.dashboard_stats()
        today_queue = database.get_todays_queue(
            config.get("daily_job_limit", 10), config
        )
        avg_score = (
            round(sum(j.get("score", 0) for j in jobs) / len(jobs), 1) if jobs else 0.0
        )
        page_stats = {
            "showing": total,
            "total": stats["total"],
            "queued": stats["queued"],
            "applied": stats["applied"],
            "emailed": stats["emailed"],
            "sql_dba": stats["sql_dba"],
            "python": stats["python"],
            "pending_outreach": stats["pending_outreach"],
            "followups_due": stats["followups_due"],
            "today_digest": len(today_queue),
            "daily_limit": config.get("daily_job_limit", 10),
            "avg_score": avg_score,
        }
        return render_template(
            "jobs.html",
            page_title="All Jobs",
            active_nav="jobs",
            jobs=jobs,
            total=total,
            page_stats=page_stats,
            filters={"status": status, "track": track, "q": search, "sort": order},
        )

    @app.get("/jobs/<int:job_id>")
    def job_detail(job_id: int):
        from job_radar import emailer
        from job_radar.email_finder import is_trusted_source
        from job_radar.linkedin_hints import build_linkedin_hints

        job = database.get_job(job_id)
        if not job:
            abort(404)
        config = load_config()
        contacts = database.list_job_contacts(job_id)
        _, resolve_source = emailer.resolve_contact_email(job, config)
        linkedin = None
        if not job.get("contact_email") or not is_trusted_source(
            job.get("contact_source") or resolve_source
        ):
            linkedin = build_linkedin_hints(job)
        return render_template(
            "job_detail.html",
            page_title=f"{job['company']} — {job['title']}",
            active_nav="jobs",
            job=job,
            contacts=contacts,
            linkedin=linkedin,
            resolve_source=resolve_source,
        )

    @app.get("/jobs/<int:job_id>/preview")
    def outreach_preview(job_id: int):
        import os

        from dotenv import load_dotenv

        from job_radar import templates

        load_dotenv(_PKG.parent / ".env")
        job = database.get_job(job_id)
        if not job:
            abort(404)
        config = load_config()
        if job.get("contact_email"):
            from job_radar.email_finder import classify_audience

            job["outreach_audience"] = classify_audience(job["contact_email"])
        profile = {
            "YOUR_NAME": os.getenv("YOUR_NAME", "You"),
            "YOUR_EMAIL": os.getenv("YOUR_EMAIL", "") or os.getenv("SMTP_USER", ""),
            "GITHUB_URL": os.getenv("GITHUB_URL", ""),
            "PROJECT_GITHUB_URL": os.getenv("PROJECT_GITHUB_URL", ""),
            "LOOM_URL": os.getenv("LOOM_URL", ""),
            "DEMO_VIDEO_URL": os.getenv("DEMO_VIDEO_URL", ""),
            "LINKEDIN_URL": os.getenv("LINKEDIN_URL", ""),
        }
        composed = templates.compose_with_meta(job, profile, config)
        learning = database.outreach_learning_stats()
        return render_template(
            "outreach_preview.html",
            page_title=f"Preview — {job['company']}",
            active_nav="outreach",
            job=job,
            composed=composed,
            learning=learning,
        )

    @app.post("/jobs/<int:job_id>/contacts")
    def add_contacts(job_id: int):
        from job_radar.contact_import import parse_contact_lines

        if not database.get_job(job_id):
            abort(404)
        raw = request.form.get("contacts_text", "")
        parsed = parse_contact_lines(raw)
        added = database.add_job_contacts(job_id, parsed) if parsed else 0
        return redirect(url_for("job_detail", job_id=job_id, added=added))

    @app.post("/jobs/<int:job_id>/contacts/send")
    def send_contacts(job_id: int):
        import os

        from dotenv import load_dotenv

        from job_radar import emailer

        load_dotenv(_PKG.parent / ".env")
        job = database.get_job(job_id)
        if not job:
            abort(404)
        config = load_config()
        sent = 0
        for contact in database.list_job_contacts(job_id):
            if contact.get("outreach_status") == "pending":
                ok, _ = emailer.send_to_manual_contact(job, contact, config)
                if ok:
                    sent += 1
        return redirect(url_for("job_detail", job_id=job_id, sent=sent))

    @app.post("/jobs/<int:job_id>/reply")
    def set_reply(job_id: int):
        if not database.get_job(job_id):
            abort(404)
        outcome = request.form.get("outcome", "none")
        database.set_reply_outcome(job_id, outcome)
        return redirect(request.referrer or url_for("job_detail", job_id=job_id))

    @app.post("/jobs/<int:job_id>/applied")
    def mark_applied(job_id: int):
        if not database.get_job(job_id):
            abort(404)
        database.mark_applied(job_id)
        return redirect(url_for("job_detail", job_id=job_id))

    @app.post("/jobs/<int:job_id>/notes")
    def save_notes(job_id: int):
        if not database.get_job(job_id):
            abort(404)
        database.update_notes(job_id, request.form.get("notes", ""))
        return redirect(url_for("job_detail", job_id=job_id))

    @app.get("/digest")
    def digest_page():
        """In-app view of today's digest (same data as output/digest.html)."""
        config = load_config()
        queue = database.get_todays_queue(config.get("daily_job_limit", 10), config)
        stats = database.stats()
        return render_template(
            "digest.html",
            page_title="Daily Digest",
            active_nav="digest",
            queue=queue,
            stats=stats,
        )

    return app


def main() -> None:
    import os

    app = create_app()
    host = os.getenv("JOB_RADAR_HOST", "127.0.0.1")
    port = int(os.getenv("JOB_RADAR_PORT", "5000"))
    print(f"Job Radar dashboard: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
