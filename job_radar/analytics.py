"""Activity metrics and chart data for the dashboard."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def _targets(config: dict) -> dict[str, int | float]:
    activity = config.get("activity_targets") or {}
    daily = int(activity.get("applications_per_day", config.get("daily_job_limit", 10)))
    working_days = int(activity.get("working_days_per_week", 5))
    return {
        "applications_per_day": daily,
        "applications_per_week": int(
            activity.get("applications_per_week", daily * working_days)
        ),
        "working_days_per_week": working_days,
    }


def build_activity_report(config: dict) -> dict[str, Any]:
    from job_radar import database

    targets = _targets(config)
    daily_target = int(targets["applications_per_day"])
    weekly_target = int(targets["applications_per_week"])

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    applied_today = database.count_applied_on_date(today)
    applied_week = database.count_applied_since(week_start)
    emailed_week = database.count_emailed_since(week_start)
    applied_total = database.count_jobs(status="applied")
    emailed_total = database.count_jobs(emailed_only=True)
    queued = database.count_jobs(status="queued")
    followups_due = database.dashboard_stats()["followups_due"]
    followups_done = database.count_followups_completed()

    daily_series = database.applications_per_day(14)
    chart_days = [row["date"] for row in daily_series]
    chart_applied = [row["count"] for row in daily_series]
    chart_ideal = [daily_target] * len(chart_days)

    outreach_gap = max(0, applied_total - emailed_total)

    # Activity rates: actual vs ideal (as % of target, capped at 100 for gauge)
    def rate_pct(actual: int, ideal: int) -> float:
        if ideal <= 0:
            return 0.0
        return round(min(100.0, (actual / ideal) * 100), 1)

    outreach_ideal = applied_total if applied_total else 1
    followup_ideal = followups_done + followups_due if (followups_done + followups_due) else 1

    activity_rates = [
        {
            "id": "daily_apply",
            "label": "Applications today",
            "importance": "critical",
            "actual": applied_today,
            "ideal": daily_target,
            "pct": rate_pct(applied_today, daily_target),
            "hint": f"Target {daily_target}/day from config",
        },
        {
            "id": "weekly_apply",
            "label": "Applications this week",
            "importance": "critical",
            "actual": applied_week,
            "ideal": weekly_target,
            "pct": rate_pct(applied_week, weekly_target),
            "hint": f"Target {weekly_target}/week ({daily_target} x {targets['working_days_per_week']} days)",
        },
        {
            "id": "outreach",
            "label": "Outreach coverage",
            "importance": "high",
            "actual": emailed_total,
            "ideal": outreach_ideal,
            "pct": rate_pct(emailed_total, outreach_ideal),
            "hint": "Every applied job should get an email",
        },
        {
            "id": "weekly_outreach",
            "label": "Emails this week",
            "importance": "high",
            "actual": emailed_week,
            "ideal": applied_week if applied_week else daily_target,
            "pct": rate_pct(emailed_week, applied_week if applied_week else daily_target),
            "hint": "Match weekly applications with outreach",
        },
        {
            "id": "followup",
            "label": "Follow-up completion",
            "importance": "medium",
            "actual": followups_done,
            "ideal": followup_ideal,
            "pct": rate_pct(followups_done, followup_ideal),
            "hint": "Complete follow-ups when they are due",
        },
        {
            "id": "queue_burn",
            "label": "Queue processed",
            "importance": "medium",
            "actual": applied_total,
            "ideal": applied_total + queued if (applied_total + queued) else 1,
            "pct": rate_pct(
                applied_total,
                applied_total + queued if (applied_total + queued) else 1,
            ),
            "hint": "Share of tracked jobs you have acted on",
        },
    ]

    funnel = database.pipeline_funnel()
    track_mix = database.track_activity_breakdown()

    alerts = []
    if applied_today < daily_target:
        alerts.append(
            {
                "level": "warning",
                "text": f"Apply to {daily_target - applied_today} more role(s) today to hit your daily target.",
                "link": "digest",
            }
        )
    if outreach_gap > 0:
        alerts.append(
            {
                "level": "warning",
                "text": f"{outreach_gap} applied job(s) have no outreach email yet.",
                "link": "outreach",
            }
        )
    if followups_due > 0:
        alerts.append(
            {
                "level": "danger",
                "text": f"{followups_due} follow-up(s) are overdue.",
                "link": "outreach",
            }
        )
    if applied_week < weekly_target // 2 and today.weekday() >= 2:
        alerts.append(
            {
                "level": "info",
                "text": "Weekly pace is behind — prioritize today's digest over browsing new listings.",
                "link": "digest",
            }
        )

    return {
        "targets": targets,
        "applied_today": applied_today,
        "applied_week": applied_week,
        "emailed_week": emailed_week,
        "outreach_gap": outreach_gap,
        "followups_due": followups_due,
        "activity_rates": activity_rates,
        "chart_days": chart_days,
        "chart_applied": chart_applied,
        "chart_ideal": chart_ideal,
        "funnel": funnel,
        "track_mix": track_mix,
        "alerts": alerts,
    }
