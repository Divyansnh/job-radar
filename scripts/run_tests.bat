@echo off
cd /d "%~dp0.."
if not exist .venv (
    echo Run scripts\setup.bat first.
    exit /b 1
)
echo === Job Radar Tests ===
.\.venv\Scripts\pip.exe install -q -r requirements-dev.txt
echo.
echo [1/2] Unit + E2E dry-run tests (no network)...
.\.venv\Scripts\pytest.exe -v -m "not integration"
echo.
echo [2/2] Health check (no network)...
.\.venv\Scripts\python.exe -m job_radar.healthcheck
echo.
echo Optional live checks:  .\scripts\healthcheck.bat --live
echo Optional integration:  .\.venv\Scripts\pytest.exe -v -m integration
pause
