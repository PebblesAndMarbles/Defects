param(
    [string]$PythonExe = "",
    [string]$DataFile = "",
    [switch]$OpenBrowser
)

# Launcher for the probe_review.html feedback portal backend.
# Adapted from html/HTML_Feedback_Portal/run_portal.ps1 (generic template).

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

if (-not [string]::IsNullOrWhiteSpace($DataFile)) {
    $env:FEEDBACK_DATA_FILE = $DataFile
    Write-Host "Feedback CSV override: $DataFile"
}

if ($OpenBrowser) {
    Write-Host "Note: -OpenBrowser has no report page to open here -- open the" -ForegroundColor Yellow
    Write-Host "probe_review.html file for the run you're reviewing directly instead." -ForegroundColor Yellow
}

Write-Host "Starting probe_review feedback portal backend..." -ForegroundColor Cyan
Write-Host "Interpreter: $PythonExe"
Write-Host "Backend: $backendMain"
Write-Host "Status/health check: http://127.0.0.1:8000/"
Write-Host "Now open the probe_review.html report for the run you're reviewing."

& "$PythonExe" "$backendMain"
exit $LASTEXITCODE
