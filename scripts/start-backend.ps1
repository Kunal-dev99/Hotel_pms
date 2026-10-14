<#
  Start the FastAPI backend (uvicorn --reload) on Windows / OneDrive.
  Hardening: kills any orphan process tree still holding the port before starting,
  because uvicorn --reload spawns a reloader + worker that don't always die on Ctrl+C.

  Usage: .\scripts\start-backend.ps1 [-Port 8000]
#>
param([int]$Port = 8000)

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$python  = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path $backend)) { Write-Error "backend/ not found at $backend (not scaffolded yet)." }
if (-not (Test-Path $python))  { Write-Error "venv missing. Run: python -m venv backend\.venv; backend\.venv\Scripts\pip install -r backend\requirements.txt" }

# Clear orphan listeners on the port (whole process tree).
$pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $pids) {
    if ($p -and $p -ne $PID) {
        Write-Host "Port $Port held by PID $p; terminating process tree."
        & taskkill.exe /PID $p /T /F | Out-Null
    }
}

Set-Location $backend
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
