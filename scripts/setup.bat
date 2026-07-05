@echo off
cd /d "%~dp0.."
echo === Job Radar Setup ===
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)
echo Installing dependencies...
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
if not exist data mkdir data
if not exist output mkdir output
echo.
echo === Setup complete ===
echo.
echo YOUR TURN:
echo   1. Edit .env  - Gmail App Password, name, GitHub, Loom
echo   2. Add PDFs to assets\  - resume_python_junior.pdf, resume_sql_dba_junior.pdf
echo   3. Run:  .\.venv\Scripts\python.exe -m job_radar.daily
echo   4. Open:  output\digest.html
echo.
pause
