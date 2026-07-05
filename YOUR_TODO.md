# YOUR TURN — 3 steps to finish setup

Project path: `C:\Users\6137711\Projects\job-radar`

## Step 1: Install dependencies (one time)

Double-click **`scripts\setup.bat`**  
OR in PowerShell:

```powershell
cd C:\Users\6137711\Projects\job-radar
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

Requires **Python 3.10+** — https://www.python.org/downloads/ (tick "Add to PATH")

---

## Step 2: Edit `.env` (one time)

Open `C:\Users\6137711\Projects\job-radar\.env` and replace:

| Field | What to put |
|-------|-------------|
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | [Gmail App Password](https://myaccount.google.com/apppasswords) (16 chars) |
| `YOUR_NAME` | Your full name |
| `YOUR_EMAIL` | Same Gmail |
| `GITHUB_URL` | Your GitHub profile |
| `LOOM_URL` | Your 60-sec intro video (or leave placeholder for now) |

---

## Step 3: Add resumes (one time)

Copy your PDFs into `assets\`:

- `assets\resume_python_junior.pdf`
- `assets\resume_sql_dba_junior.pdf`

---

## Test run

```powershell
cd C:\Users\6137711\Projects\job-radar
.\scripts\run_tests.bat
```

This runs **all unit tests + E2E dry-run + health check** (no network).

### Full verification levels

| Command | What it checks | Network |
|---------|----------------|---------|
| `scripts\run_tests.bat` | Setup files, scorer, DB, email mocks, E2E pipeline | No |
| `python -m job_radar.healthcheck` | Same as above in one report | No |
| `python -m job_radar.healthcheck --live` | + live Razorpay ATS + Naukri scrape | Yes |
| `pytest -v -m integration` | Live ATS + portal only | Yes |
| `python -m job_radar.daily` | **Real daily run** — production | Yes |

---

## First real run

---

## Schedule daily 8 AM (optional)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

---

## Daily routine (~20 min)

1. Open `output\digest.html`
2. Click **Apply** on each job
3. Done — emails and follow-ups run automatically if Step 2 is done
