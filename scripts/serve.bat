@echo off
cd /d "%~dp0.."
if not exist .venv (
    echo Run scripts\setup.bat first.
    exit /b 1
)
echo Stopping any old server on port 5000...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
echo.
echo Starting Job Radar dashboard at http://127.0.0.1:5000
echo Hard-refresh in browser if the page looks old: Ctrl+F5
echo.
.\.venv\Scripts\python.exe -m job_radar.web
