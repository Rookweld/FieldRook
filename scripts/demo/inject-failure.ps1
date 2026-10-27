# Inject the controlled demo failure (Scenario B setup).
# Technician-side scaffolding: creates the incident FieldRook then diagnoses.
# Run: powershell -ExecutionPolicy Bypass -File scripts/demo/inject-failure.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = if ($env:FIELDROOK_PYTHON) { $env:FIELDROOK_PYTHON } else { Join-Path $root "backend\.venv\Scripts\python.exe" }
$heartbeat = Join-Path $root "demo_worker\state\heartbeat.json"

if (-not (Test-Path $heartbeat)) { throw "Demo worker is not running. Run scripts/demo/start-worker.ps1 first." }
& $python (Join-Path $root "demo_worker\simulate_failure.py")
Start-Sleep -Seconds 4
$hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
if ($hb.status -ne "failed") { throw "Worker did not report failed (status=$($hb.status))." }
Write-Host "Failure injected: status=$($hb.status) detail='$($hb.detail)'."
