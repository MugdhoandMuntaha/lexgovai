# LexGOV AI Quick Start Script
param (
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $FrontendOnly) {
    Write-Host "`n[1/2] Starting Backend API on http://localhost:8000..." -ForegroundColor Cyan
    $backendDir = Join-Path $Root "backend"
    $pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Host "Creating Python venv in $backendDir\.venv..." -ForegroundColor Yellow
        py -3.14 -m venv "$backendDir\.venv"
        & $pythonExe -m pip install -q -r "$backendDir\requirements.txt"
    }

    # One-time check: install Playwright Chromium browser binary if needed
    $playwrightCache = Join-Path $env:LOCALAPPDATA "ms-playwright\chromium*"
    if (-not (Test-Path $playwrightCache)) {
        Write-Host "Installing Playwright Chromium browser binary for government portal crawling..." -ForegroundColor Yellow
        & $pythonExe -m playwright install chromium
    }

    Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "app.main:create_app", "--factory", "--reload", "--port", "8000" -WorkingDirectory $backendDir
    Start-Process -FilePath $pythonExe -ArgumentList "-m", "app.worker" -WorkingDirectory $backendDir
    Write-Host "Backend API and Worker Daemon started in background windows." -ForegroundColor Green
}

if (-not $BackendOnly) {
    Write-Host "`n[2/2] Starting Frontend on http://localhost:3000..." -ForegroundColor Cyan
    $frontendDir = Join-Path $Root "frontend"
    Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $frontendDir
    Write-Host "Frontend started in background window." -ForegroundColor Green
}

Write-Host "`nLexGOV AI is running!" -ForegroundColor Green
Write-Host "- Frontend: http://localhost:3000"
Write-Host "- Backend Docs: http://localhost:8000/docs"
Write-Host "- Offline tests: cd backend; .\.venv\Scripts\python.exe -m pytest -q`n"

