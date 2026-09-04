@echo off
REM Double-click wrapper for run_portal.ps1 — HTML Feedback Portal template.
REM Adapted from the PCSA flag_disposition_portal run_portal.cmd.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_portal.ps1" -OpenBrowser
pause
