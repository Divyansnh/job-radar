# Register Windows Task Scheduler job — runs Job Radar daily at 8:00 AM

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Daily = "-m job_radar.daily"

if (-not (Test-Path $Python)) {
    Write-Host "Virtual env not found. Run setup first:"
    Write-Host "  cd $ProjectRoot"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements.txt"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument $Daily -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "JobRadar-Daily" -Action $Action -Trigger $Trigger -Settings $Settings -Force

Write-Host "Scheduled task 'JobRadar-Daily' registered for 8:00 AM daily."
