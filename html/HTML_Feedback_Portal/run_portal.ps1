param(
    [string]$PythonExe = "",
    [switch]$OpenBrowser
)

# Generic launcher for the HTML Feedback Portal template.
# Adapted from the PCSA flag_disposition_portal run_portal.ps1
# (agents_history session 2026-08-07_003, PCSA workspace).

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendMain = Join-Path $scriptRoot "backend\main.py"

if (-not (Test-Path $backendMain)) {
    Write-Error "Cannot find backend entry point: $backendMain"
}

if ([string]::IsNullOrWhiteSpace($PythonExe) -or -not (Test-Path $PythonExe)) {
    # Discovery order: explicit -PythonExe param -> common USERPROFILE
    # install locations -> `where python` on PATH. Customize the
    # candidate paths below for your environment if needed.
    $candidates = @(
        "$env:USERPROFILE\My Programs\SQLPathFinder3\Python3\python.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\python.exe"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) {
        $PythonExe = $found
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCmd) {
            Write-Host "Python executable not found." -ForegroundColor Red
            Write-Host "Install Python or pass a path with -PythonExe."
            exit 1
        }
        $PythonExe = $pythonCmd.Source
    }
}

# Verify Flask is available in the chosen interpreter before launch.
$flaskCheck = & "$PythonExe" -c "import flask" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Flask import failed for interpreter: $PythonExe" -ForegroundColor Red
    Write-Host "Install Flask in that interpreter (pip install flask) or provide a different -PythonExe path."
    Write-Host $flaskCheck
    exit 1
}

if ($OpenBrowser) {
    Start-Process "http://127.0.0.1:8000/"
}

Write-Host "Starting HTML Feedback Portal..." -ForegroundColor Cyan
Write-Host "Interpreter: $PythonExe"
Write-Host "Backend: $backendMain"
Write-Host "URL: http://127.0.0.1:8000/  (open this URL — do not double-click index.html)"

& "$PythonExe" "$backendMain"
exit $LASTEXITCODE
