# FieldRook demo preflight: verify the machine is ready for Scenario A/B/C.
# Read-only: never starts, stops, or modifies anything.
# Run: powershell -ExecutionPolicy Bypass -File scripts/demo/preflight.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$fail = 0

function Check([string]$Name, [scriptblock]$Test, [string]$Hint = "") {
    try {
        $ok = & $Test
    } catch {
        $ok = $false
    }
    if ($ok) {
        Write-Host "[OK] $Name" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $Name $Hint" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "FieldRook demo preflight (root: $root)"
Check "Repo root exists" { Test-Path (Join-Path $root "README.md") }
Check "Backend python available" { if ($env:FIELDROOK_PYTHON) { $true } else { Test-Path (Join-Path $root "backend\.venv\Scripts\python.exe") } } "(run: python -m venv backend\.venv; pip install -r backend\requirements.txt; or set FIELDROOK_PYTHON)"
Check "Frontend deps installed" { Test-Path (Join-Path $root "frontend\node_modules") } "(run: pnpm install in frontend\)"
Check "Port 8000 free or FieldRook" {
    $c = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    -not $c
} "(stop whatever holds :8000, or reuse it if it is FieldRook)"
Check "Port 5173 free" {
    $c = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    -not $c
} "(stop the holder or reuse the running Vite server)"

$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
    $hasKey = (Get-Content $envPath | Select-String -Pattern '^MODEL_API_KEY=\S+')
    if ($hasKey) { Write-Host "[OK] .env with MODEL_API_KEY (live Meta mode available)" -ForegroundColor Green }
    else { Write-Host "[WARN] .env exists but MODEL_API_KEY is empty (simulated mode only)" -ForegroundColor Yellow }
} else {
    Write-Host "[WARN] No .env (simulated fixture mode only; copy .env.example to .env for live Meta)" -ForegroundColor Yellow
}

$hb = Join-Path $root "demo_worker\state\heartbeat.json"
if (Test-Path $hb) {
    $status = (Get-Content $hb -Raw | ConvertFrom-Json).status
    Write-Host "[INFO] Demo worker heartbeat present, status=$status"
} else {
    Write-Host "[INFO] Demo worker not running yet (start with scripts/demo/start-worker.ps1)"
}

if ($fail -gt 0) { Write-Host "$fail blocking check(s) failed." -ForegroundColor Red; exit 1 }
Write-Host "Preflight passed." -ForegroundColor Green
