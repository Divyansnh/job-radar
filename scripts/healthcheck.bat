@echo off
cd /d "%~dp0.."
if not exist .venv (
    echo Run scripts\setup.bat first.
    exit /b 1
)
echo === Job Radar Health Check ===
if "%1"=="--live" (
    echo Mode: live ^(network^)
    .\.venv\Scripts\python.exe -m job_radar.healthcheck --live
) else (
    echo Mode: local ^(no network^)
    .\.venv\Scripts\python.exe -m job_radar.healthcheck
)
exit /b %ERRORLEVEL%
