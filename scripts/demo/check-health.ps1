# Show demo health: worker heartbeat + backend status (if reachable).
# Read-only.
# Run: powershell -ExecutionPolicy Bypass -File scripts/demo/check-health.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$heartbeat = Join-Path $root "demo_worker\state\heartbeat.json"

if (Test-Path $heartbeat) {
    $hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
    $age = [Math]::Max(0, [int]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $hb.updated_at))
    Write-Host "worker: status=$($hb.status) pid=$($hb.pid) heartbeat_age=${age}s detail='$($hb.detail)'"
} else {
    Write-Host "worker: NOT RUNNING (no heartbeat)"
}

try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -TimeoutSec 5
    Write-Host ("backend: model_mode={0} model={1} live_diagnostics={2}" -f $r.model_mode, $r.model_name, $r.live_diagnostics_available)
} catch {
    Write-Host "backend: NOT REACHABLE on 127.0.0.1:8000"
}
