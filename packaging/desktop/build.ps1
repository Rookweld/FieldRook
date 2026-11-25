<# FieldRook Desktop reproducible build (M025 BETA).
Builds the frozen one-dir desktop bundle from this checkout:
  frontend (pnpm build) -> worker one-dir -> server one-dir (+worker data)
  -> assembled FieldRook-<VERSION>\ dir + SHA256SUMS.txt + BOM.txt.

Build pins live HERE (M025 toolchain contract). No code signing (not
authorized); the BOM states that. Requires: Windows, Python 3.12+,
Node+pnpm (unless -SkipFrontend with a prebuilt frontend\dist).

Usage (from the repo root):
  powershell -ExecutionPolicy Bypass -File packaging\desktop\build.ps1 [-OutDir <dir>] [-SkipFrontend] [-PythonExe <Python3.12>]

Outputs (default OutDir: packaging\desktop\dist):
  dist\FieldRook-<VERSION>\           portable install dir (zip it to ship)
  dist\FieldRook-<VERSION>.zip        shippable archive
  dist\SHA256SUMS.txt                 hashes of the archive + exes
  dist\BOM.txt                        tool versions + artifact hashes
#>
[CmdletBinding()]
param(
    [string]$OutDir = "",
    [switch]$SkipFrontend,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------ pins --
$PyInstallerPin = "pyinstaller==6.22.3"
$ReleasePythonMajor = 3
$ReleasePythonMinor = 12

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PackagingDir)
$ReleaseRequirements = Join-Path $RepoRoot "backend\requirements-release.txt"
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $PackagingDir "dist" }
$OutDir = [IO.Path]::GetFullPath($OutDir)
$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim().Split("`n")[0].Trim()
if ([string]::IsNullOrWhiteSpace($Version)) { throw "VERSION file is empty." }

$WorkRoot = Join-Path $OutDir "_work"
$BuildVenv = Join-Path $WorkRoot "build-venv"
$FreezeOut = Join-Path $WorkRoot "freeze"
$AssembleDir = Join-Path $OutDir ("FieldRook-" + $Version)

Write-Host "FieldRook Desktop build $Version (repo $RepoRoot)"

# ------------------------------------------------------------- prerequisites
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $testedPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
    if (Test-Path $testedPython) {
        $PythonExe = $testedPython
    } else {
        throw "Explicit -PythonExe is required when the checkout's tested backend\.venv is absent. Use Python 3.12."
    }
}
$pythonExe = (Resolve-Path -LiteralPath $PythonExe -ErrorAction Stop).Path
$pyVersion = [Version](& $pythonExe -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
if ($LASTEXITCODE -ne 0) { throw "Cannot execute build Python: $pythonExe" }
if ($pyVersion.Major -ne $ReleasePythonMajor -or $pyVersion.Minor -ne $ReleasePythonMinor) {
    throw "Release build requires Python 3.12.x (got $pyVersion from $pythonExe)."
}
if (-not (Test-Path $ReleaseRequirements)) { throw "Release dependency lock missing: $ReleaseRequirements" }
Write-Host "Pinned Python: $pyVersion ($pythonExe)"
Write-Host "Release dependencies: $ReleaseRequirements"
# The BOM must identify the exact source tree, not silently label dirty code
# with the HEAD commit. The packaging stage is intentionally source-clean.
$sourceStatus = @(git -C $RepoRoot status --porcelain=v1)
if ($LASTEXITCODE -ne 0) { throw "Cannot inspect source Git state." }
if ($sourceStatus.Count -gt 0) { throw "Refusing release build from an uncommitted tree; commit and review changes first." }

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
if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed." }
& $buildPython -m pip install --quiet -r $ReleaseRequirements
if ($LASTEXITCODE -ne 0) { throw "Pinned runtime requirements installation failed." }
& $buildPython -m pip install --quiet $PyInstallerPin
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }
& $buildPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "Build dependency graph has broken requirements." }
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
FieldRook Desktop $Version — portable edition.
Launch FieldRook.exe (WPF + WebView2); keep the server folder beside the executable.
Windows 10/11 x64 and Microsoft Edge WebView2 Runtime are required.
Data and diagnostic logs are stored separately in %LOCALAPPDATA%\FieldRook.
No Python, Node, or admin privileges are required on the target.
For Start Menu integration and registered uninstall, use the separate
FieldRook-Setup-$Version.exe installer (if provided).
This ZIP is portable: extract the entire folder before starting FieldRook.
Do not delete %LOCALAPPDATA%\FieldRook when upgrading or removing binaries.
"@ | Set-Content (Join-Path $AssembleDir "README.txt")

$zipPath = Join-Path $OutDir ("FieldRook-" + $Version + ".zip")
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path $AssembleDir -DestinationPath $zipPath

# ------------------------------------------------- checksums + release BOM --
function Get-Sha256Hex {
    # .NET hashing (works on PS 5.1/7+, incl. constrained hosts without Get-FileHash).
    param([string]$Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try {
            $bytes = $sha.ComputeHash($stream)
        } finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace("-", "").ToLower()
}

$artifacts = @($zipPath, (Join-Path $AssembleDir "server\FieldRook-Server.exe"), $bundledWorker.Replace($serverDist, (Join-Path $AssembleDir "server")))
$checksums = foreach ($file in $artifacts) {
    $hash = Get-Sha256Hex -Path $file
    "$hash  $(Split-Path -Leaf $file)"
}
$checksums | Set-Content (Join-Path $OutDir "SHA256SUMS.txt")

$gitCommit = ""
try { $gitCommit = (git -C $RepoRoot rev-parse HEAD 2>$null).Trim() } catch { $gitCommit = "unknown" }
$freezeList = (& $buildPython -m pip freeze) -join "`n"
$releaseLockSha256 = Get-Sha256Hex -Path $ReleaseRequirements
@"
FieldRook Desktop $Version — build BOM (M025)
=============================================
version:        $Version
git commit:     $gitCommit
built on:       $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
builder python: $pyVersion ($pythonExe)
release lock:   backend/requirements-release.txt (sha256 $releaseLockSha256)
source state:   clean (at build start)
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
