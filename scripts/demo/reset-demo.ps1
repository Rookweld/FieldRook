# Reset the demo to a healthy worker. Never touches saved investigations.
# - Writes a healthy control file (same mechanism the approved recovery uses).
# - Starts the worker if it is not running.
# - Verifies a fresh healthy heartbeat.
# Run: powershell -ExecutionPolicy Bypass -File scripts/demo/reset-demo.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$stateDir = Join-Path $root "demo_worker\state"
$heartbeat = Join-Path $stateDir "heartbeat.json"
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
# .NET write: BOM-free UTF-8 on both Windows PowerShell 5.1 and PowerShell 7+.
[System.IO.File]::WriteAllText(
    (Join-Path $stateDir "control.json"),
    '{"mode": "healthy"}',
    (New-Object System.Text.UTF8Encoding $false))
Write-Host "Control reset to healthy."

& (Join-Path $PSScriptRoot "start-worker.ps1")
Start-Sleep -Seconds 3
$hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
if ($hb.status -ne "healthy") { throw "Worker still not healthy (status=$($hb.status))." }
Write-Host "Demo reset complete: worker healthy. Saved investigations untouched."
