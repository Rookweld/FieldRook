<# FieldRook Desktop reproducible build (M025 BETA).
Builds the frozen one-dir desktop bundle from this checkout:
  frontend (pnpm build) -> worker one-dir -> server one-dir (+worker data)
  -> assembled FieldRook-<VERSION>\ dir + SHA256SUMS.txt + BOM.txt.

Build pins live HERE (M025 toolchain contract). No code signing (not
authorized); the BOM states that. Requires: Windows, Python 3.12+,
Node+pnpm (unless -SkipFrontend with a prebuilt frontend\dist).

Usage (from the repo root):
  powershell -ExecutionPolicy Bypass -File packaging\desktop\build.ps1 [-OutDir <dir>] [-SkipFrontend]

Outputs (default OutDir: packaging\desktop\dist):
  dist\FieldRook-<VERSION>\           portable install dir (zip it to ship)
  dist\FieldRook-<VERSION>.zip        shippable archive
  dist\SHA256SUMS.txt                 hashes of the archive + exes
  dist\BOM.txt                        tool versions + artifact hashes
#>
[CmdletBinding()]
param(
    [string]$OutDir = "",
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------ pins --
$PyInstallerPin = "pyinstaller==6.22.3"
$MinPython = [Version]"3.12.0"

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PackagingDir)
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $PackagingDir "dist" }
$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim().Split("`n")[0].Trim()
if ([string]::IsNullOrWhiteSpace($Version)) { throw "VERSION file is empty." }

$WorkRoot = Join-Path $OutDir "_work"
$BuildVenv = Join-Path $WorkRoot "build-venv"
$FreezeOut = Join-Path $WorkRoot "freeze"
$AssembleDir = Join-Path $OutDir ("FieldRook-" + $Version)

Write-Host "FieldRook Desktop build $Version (repo $RepoRoot)"

# ------------------------------------------------------------- prerequisites
$pythonExe = (Get-Command python.exe -ErrorAction Stop).Source
$pyVersion = [Version](& $pythonExe -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
if ($pyVersion -lt $MinPython) { throw "Python $MinPython+ required (found $pyVersion)." }
Write-Host "Python: $pyVersion ($pythonExe)"

$frontendDist = Join-Path $RepoRoot "frontend\dist\index.html"
if (-not $SkipFrontend) {
    Write-Host "Building frontend..."
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        & pnpm run build
        if ($LASTEXITCODE -ne 0) { throw "pnpm run build failed." }
    } finally { Pop-Location }
}
if (-not (Test-Path $frontendDist)) {
    throw "frontend\dist\index.html missing (run without -SkipFrontend, or build the frontend first)."
}

# Secret hygiene: the bundle must never ship secrets (M020 carryover).
$secretHits = @()
foreach ($name in ".env", "*.pem", "*.key", "demo_token.txt", "*.token") {
    $secretHits += Get-ChildItem -Recurse -Force -Path $RepoRoot -Filter $name -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "node_modules|\.venv|\.git|dist\\|_work\\" } |
        ForEach-Object { $_.FullName }
}
if ($secretHits.Count -gt 0) {
    Write-Host "Refusing to build: secret-like files present in the checkout:"
    $secretHits | ForEach-Object { Write-Host "  $_" }
    throw "Remove the files above (or restrict them) before building a shippable bundle."
}

# ------------------------------------------------------- isolated build env --
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
if (-not (Test-Path (Join-Path $BuildVenv "Scripts\python.exe"))) {
    Write-Host "Creating isolated build venv..."
    & $pythonExe -m venv $BuildVenv
}
$buildPython = Join-Path $BuildVenv "Scripts\python.exe"
& $buildPython -m pip install --quiet --upgrade pip
& $buildPython -m pip install --quiet -r (Join-Path $RepoRoot "backend\requirements.txt")
& $buildPython -m pip install --quiet $PyInstallerPin
$installedPyInstaller = (& $buildPython -m pip show pyinstaller | Select-String "^Version:").ToString().Split(":")[1].Trim()
Write-Host "PyInstaller: $installedPyInstaller"

# ------------------------------------------------------------------ freeze --
Push-Location $PackagingDir
try {
    Write-Host "Freezing demo worker (one-dir)..."
    & $buildPython -m PyInstaller --noconfirm --clean `
        --distpath (Join-Path $FreezeOut "dist") --workpath (Join-Path $FreezeOut "work-worker") `
        fieldrook-demo-worker.spec
    if ($LASTEXITCODE -ne 0) { throw "worker freeze failed." }
    $workerDist = Join-Path $FreezeOut "dist\fieldrook-demo-worker"
    if (-not (Test-Path (Join-Path $workerDist "fieldrook-demo-worker.exe"))) {
        throw "worker exe missing after freeze: $workerDist"
    }
    Write-Host "Freezing server (one-dir, worker bundled as data)..."
    $env:FIELDROOK_WORKER_DIST = $workerDist
    & $buildPython -m PyInstaller --noconfirm --clean `
        --distpath (Join-Path $FreezeOut "dist") --workpath (Join-Path $FreezeOut "work-server") `
        fieldrook-server.spec
    if ($LASTEXITCODE -ne 0) { throw "server freeze failed." }
} finally { Pop-Location }
$serverDist = Join-Path $FreezeOut "dist\FieldRook-Server"
$serverExe = Join-Path $serverDist "FieldRook-Server.exe"
if (-not (Test-Path $serverExe)) { throw "server exe missing after freeze: $serverExe" }

# Frozen smoke: --version must print the VERSION file, and the bundled
# worker exe must exist at the paths.py contract location.
$smokeVersion = (& $serverExe --version).Trim()
if ($smokeVersion -ne $Version) { throw "frozen --version mismatch: '$smokeVersion' vs '$Version'." }
$bundledWorker = Join-Path $serverDist "_internal\demo-worker\fieldrook-demo-worker.exe"
if (-not (Test-Path $bundledWorker)) { throw "bundled worker exe missing: $bundledWorker" }
Write-Host "Frozen smoke OK (--version $smokeVersion, worker bundled)."

# ---------------------------------------------------------------- assemble --
if (Test-Path $AssembleDir) { Remove-Item -Recurse -Force $AssembleDir }
New-Item -ItemType Directory -Force -Path $AssembleDir | Out-Null
Copy-Item (Join-Path $PackagingDir "FieldRook.bat") $AssembleDir
Copy-Item (Join-Path $PackagingDir "FieldRook-Launcher.ps1") $AssembleDir
Copy-Item $serverDist (Join-Path $AssembleDir "server") -Recurse
@"
FieldRook Desktop $Version (M025 field kit).
Run FieldRook.bat. Data + logs live in %LOCALAPPDATA%\FieldRook.
No installer, no admin, localhost only. See docs\FIELD_KIT.md (GAMMA).
"@ | Set-Content (Join-Path $AssembleDir "README.txt")

$zipPath = Join-Path $OutDir ("FieldRook-" + $Version + ".zip")
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path $AssembleDir -DestinationPath $zipPath

# ------------------------------------------------- checksums + release BOM --
$artifacts = @($zipPath, (Join-Path $AssembleDir "server\FieldRook-Server.exe"), $bundledWorker.Replace($serverDist, (Join-Path $AssembleDir "server")))
$checksums = foreach ($file in $artifacts) {
    $hash = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLower()
    "$hash  $(Split-Path -Leaf $file)"
}
$checksums | Set-Content (Join-Path $OutDir "SHA256SUMS.txt")

$gitCommit = ""
try { $gitCommit = (git -C $RepoRoot rev-parse HEAD 2>$null).Trim() } catch { $gitCommit = "unknown" }
$freezeList = (& $buildPython -m pip freeze) -join "`n"
@"
FieldRook Desktop $Version — build BOM (M025)
=============================================
version:        $Version
git commit:     $gitCommit
built on:       $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
builder python: $pyVersion ($pythonExe)
pyinstaller:    $installedPyInstaller (pinned: $PyInstallerPin)
signing:        NONE (not authorized — see M025 contracts)
console:        server ON (errors visible), worker OFF (detached)

checksums (sha256):
$($checksums -join "`n")

build-env pip freeze:
$freezeList
"@ | Set-Content (Join-Path $OutDir "BOM.txt")

Write-Host ""
Write-Host "Build OK: $AssembleDir"
Write-Host "Archive:  $zipPath"
Write-Host "BOM:      $(Join-Path $OutDir 'BOM.txt')"
