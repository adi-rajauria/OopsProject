# Start the Decerno web UI (Windows PowerShell). Usage: .\run_frontend.ps1   (backend must be running on :8000)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "frontend")
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies (npm ci) ..."
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
}
npm run dev -- --host 127.0.0.1
