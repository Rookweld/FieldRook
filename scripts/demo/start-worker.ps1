# Start the FieldRook demo worker (application-owned, ordinary user rights).
# Idempotent: does nothing if a live heartbeat already exists.
# Run: powershell -ExecutionPolicy Bypass -File scripts/demo/start-worker.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = if ($env:FIELDROOK_PYTHON) { $env:FIELDROOK_PYTHON } else { Join-Path $root "backend\.venv\Scripts\python.exe" }
$worker = Join-Path $root "demo_worker\worker.py"
$stateDir = Join-Path $root "demo_worker\state"
$heartbeat = Join-Path $stateDir "heartbeat.json"

if (-not (Test-Path $python)) { throw "Backend venv missing: $python" }
if (Test-Path $heartbeat) {
    $hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
    $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $hb.updated_at
    if ($age -lt 10) {
        Write-Host "Demo worker already running (status=$($hb.status), pid=$($hb.pid), age=${age}s)."
        exit 0
    }
    Write-Host "Stale heartbeat (age=${age}s); starting a fresh worker."
}

$log = Join-Path $stateDir "worker.log"
$proc = Start-Process -FilePath $python -ArgumentList "`"$worker`"" -WorkingDirectory $root `
    -RedirectStandardOutput $log -RedirectStandardError "$stateDir\worker.err.log" -PassThru -WindowStyle Hidden
Write-Host "Started demo worker pid=$($proc.Id) (log: $log)."
Start-Sleep -Seconds 3
$hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
Write-Host "Heartbeat: status=$($hb.status) pid=$($hb.pid)."
