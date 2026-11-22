# Start the I-ITSM API (Windows PowerShell). Usage: .\run_backend.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "backend")

$python = if ($env:PYTHON) { $env:PYTHON } else { "py -3.14" }
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment with $python ..."
    Invoke-Expression "$python -m venv .venv"
}
$venvPython = ".\.venv\Scripts\python.exe"
& $venvPython -m pip --version *> $null
if ($LASTEXITCODE -ne 0) { & $venvPython -m ensurepip --upgrade | Out-Null }
& $venvPython -m pip install --quiet --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (-not (Test-Path ".env")) {
    Write-Host "backend\.env is missing. Run: Copy-Item backend\.env.example backend\.env  (then set ITSM_DATABASE_URL and ITSM_JWT_SECRET)"
    exit 1
}

& ".\.venv\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed" }
# Live-update (SSE) streams never end on their own; without a shutdown timeout a code reload waits for them forever.
& ".\.venv\Scripts\uvicorn.exe" app.main:create_app --factory --reload --timeout-graceful-shutdown 3 --host 127.0.0.1 --port 8000
