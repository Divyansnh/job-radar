# One-time setup script for Job Radar

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== Job Radar Setup ===" -ForegroundColor Cyan

# Config files
if (-not (Test-Path "config.yaml")) {
    Copy-Item "config.example.yaml" "config.yaml"
    Write-Host "Created config.yaml"
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env — EDIT THIS with your Gmail and profile details"
}

# Virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
& ".\.venv\Scripts\pip.exe" install -r requirements.txt
& ".\.venv\Scripts\pip.exe" install -r requirements-dev.txt

# Folders
New-Item -ItemType Directory -Force -Path "data", "output", "assets" | Out-Null

Write-Host ""
Write-Host "=== Next steps ===" -ForegroundColor Green
Write-Host "1. Edit .env with your Gmail App Password and profile"
Write-Host "2. Add resumes to assets\resume_python_junior.pdf and assets\resume_sql_dba_junior.pdf"
Write-Host "3. Test run:  .\.venv\Scripts\python.exe -m job_radar.daily"
Write-Host "4. Open output\digest.html"
Write-Host "5. Schedule:  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1"
