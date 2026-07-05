$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\.venv\Scripts\pytest.exe")) {
    Write-Host "Run scripts\setup.bat first."
    exit 1
}

& ".\.venv\Scripts\pip.exe" install -q -r requirements-dev.txt

Write-Host "`n[1/2] Unit + E2E dry-run tests (no network)..." -ForegroundColor Cyan
& ".\.venv\Scripts\pytest.exe" -v -m "not integration"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[2/2] Health check (no network)..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m job_radar.healthcheck
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nOptional:" -ForegroundColor Green
Write-Host "  python -m job_radar.healthcheck --live"
Write-Host "  pytest -v -m integration"
