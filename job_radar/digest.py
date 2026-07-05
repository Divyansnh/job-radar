"""Generate HTML daily digest."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def render_digest(jobs: list[dict[str, Any]], stats: dict[str, int]) -> str:
    today = datetime.now().strftime("%A, %d %B %Y")
    rows = ""
    for j in jobs:
        score = j.get("score", 0)
        email_status = j.get("outreach_status", "pending")
        rows += f"""
        <tr>
          <td><strong>{j.get('company', '')}</strong></td>
          <td>{j.get('title', '')}</td>
          <td>{j.get('location', 'Any')}</td>
          <td>{j.get('track', '')}</td>
          <td>{j.get('source', '')}</td>
          <td>{score}</td>
          <td>{email_status}</td>
          <td><a href="{j.get('job_url', '#')}" target="_blank">Apply</a></td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="8">No new jobs today — check back tomorrow.</td></tr>'

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Job Radar — {today}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f8f9fa; }}
    h1 {{ color: #1a1a2e; }}
    .stats {{ background: #fff; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
    th {{ background: #1a1a2e; color: #fff; }}
    a {{ color: #2563eb; }}
    tr:hover {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <h1>Job Radar — {today}</h1>
  <div class="stats">
    <strong>Today's queue:</strong> {len(jobs)} jobs &nbsp;|&nbsp;
    <strong>All time tracked:</strong> {stats.get('total', 0)} &nbsp;|&nbsp;
    <strong>Applied:</strong> {stats.get('applied', 0)} &nbsp;|&nbsp;
    <strong>Emails sent:</strong> {stats.get('emailed', 0)}
  </div>
  <p>Apply to each link below (~20 min). Emails and follow-ups run automatically if Gmail is configured.</p>
  <table>
    <thead>
      <tr>
        <th>Company</th>
        <th>Role</th>
        <th>Location</th>
        <th>Track</th>
        <th>Source</th>
        <th>Score</th>
        <th>Email</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>"""


def write_digest(jobs: list[dict[str, Any]], stats: dict[str, int], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_digest(jobs, stats), encoding="utf-8")
