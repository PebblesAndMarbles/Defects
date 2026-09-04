@echo off
REM Double-click wrapper for run_portal.ps1 -- probe_review.html feedback portal.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_portal.ps1"
pause
