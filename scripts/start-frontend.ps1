<#
  Start the Next.js frontend (npm run dev) on Windows / OneDrive.
  Hardening:
    - Kills any orphan process still holding the dev port.
    - Wipes .next with Remove-Item -Force (follows OneDrive placeholder files silently;
      plain `rmdir /s /q` errors or hangs on cloud-only placeholders).

  Usage: .\scripts\start-frontend.ps1 [-Port 3000]
#>
param([int]$Port = 3000)

$ErrorActionPreference = 'Stop'
$root     = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'frontend'

if (-not (Test-Path $frontend)) { Write-Error "frontend/ not found at $frontend (not scaffolded yet)." }

$pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $pids) {
    if ($p -and $p -ne $PID) {
        Write-Host "Port $Port held by PID $p; terminating process tree."
        & taskkill.exe /PID $p /T /F | Out-Null
    }
}

$next = Join-Path $frontend '.next'
if (Test-Path $next) {
    Write-Host 'Clearing .next'
    Remove-Item -LiteralPath $next -Recurse -Force -ErrorAction SilentlyContinue
}

Set-Location $frontend
if (-not (Test-Path 'node_modules')) { npm install }
npm run dev -- --port $Port
