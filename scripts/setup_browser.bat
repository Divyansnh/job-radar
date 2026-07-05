@echo off
cd /d "%~dp0.."
echo Installing Playwright Python package...
.\.venv\Scripts\pip.exe install -r requirements-browser.txt
echo.
echo Installing Chromium browser...
.\.venv\Scripts\playwright.exe install chromium
echo.
echo Done. Next, save login sessions:
echo   .\.venv\Scripts\python.exe scripts\save_browser_session.py naukri
echo   .\.venv\Scripts\python.exe scripts\save_browser_session.py hirist
pause
