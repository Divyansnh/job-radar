# Job Radar

Automated job search for **Junior Python Backend** and **Junior SQL DBA** roles.

> **Start here:** open [`YOUR_TODO.md`](YOUR_TODO.md) for the 3 steps only you can complete.

## How it works (daily)

```
8:00 AM  Tier 1 → Check company career pages (Greenhouse / Lever / Ashby APIs)
8:15 AM  Tier 2 → Scan job portals (Naukri, Hirist, LinkedIn via JobSpy)
8:30 AM  Merge → Filter, score, dedupe → pick top 10
         You   → Open output/digest.html → apply (~20 min)
         Auto  → Send outreach emails + follow-ups on Day 3, 7, 12
```

## One-time setup

### 1. Install Python 3.10+

Download from https://www.python.org/downloads/ — check "Add to PATH".

### 2. Install dependencies

```powershell
cd C:\Users\6137711\Projects\job-radar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure your profile

```powershell
copy .env.example .env
copy config.example.yaml config.yaml
```

Edit `.env` with your Gmail App Password and personal details.
Edit `config.yaml` if you want to change daily job count or filters.

### 4. Add your resumes

Place PDFs in `assets/`:
- `assets/resume_python_junior.pdf`
- `assets/resume_sql_dba_junior.pdf`

### 5. Run manually (test first)

```powershell
python -m job_radar.daily
```

Open `output/digest.html` in your browser.

### 6. Schedule daily run (Windows Task Scheduler)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

Runs every day at 8:00 AM.

## Your daily routine (~20 min)

1. Open `output/digest.html`
2. Click **Apply** on each job link (up to 10)
3. Mark jobs as applied in digest (or they auto-mark when email sends)
4. Done — follow-ups are automatic

## Project structure

```
job-radar/
├── config.yaml           # Your filters, role keywords, daily limit
├── companies.yaml        # 60+ companies to check daily (ATS APIs)
├── .env                  # Gmail credentials (you fill in)
├── job_radar/
│   ├── daily.py          # Main entry point — run this daily
│   ├── ats_fetcher.py    # Tier 1: company career page APIs
│   ├── portal_scraper.py # Tier 2: Naukri, LinkedIn, etc.
│   ├── scorer.py         # Score & filter jobs
│   ├── database.py       # SQLite tracker
│   ├── emailer.py        # Outreach + 3 follow-ups
│   ├── templates.py      # Email templates
│   └── digest.py         # HTML daily digest
├── data/tracker.db       # Auto-created — all jobs tracked here
└── output/digest.html    # Today's jobs — open this each morning
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `0 jobs found` | Job boards may be rate-limiting; run again in 1 hour |
| Email not sending | Check Gmail App Password in `.env` |
| `python not found` | Install Python 3.10+ and add to PATH |
| Import errors | Activate venv: `.\.venv\Scripts\Activate.ps1` |
