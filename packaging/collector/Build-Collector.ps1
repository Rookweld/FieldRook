<#
.SYNOPSIS
    Reproducible one-dir build of FieldRook-Collector.exe (M025 ALPHA).
.DESCRIPTION
    Creates an isolated build venv, installs the pinned PyInstaller from
    requirements-build.txt, freezes the stdlib-only collector package into a
    portable console exe (one-dir), smoke-tests it (--help + validate of the
    committed sample), and writes README.txt + SHA256SUMS.txt + BUILD-BOM.txt
    into the portable dir. No code signing (not authorized for M025).

    Run from anywhere; paths resolve from this script's location:
      powershell -ExecutionPolicy Bypass -File packaging/collector/Build-Collector.ps1
.PARAMETER OutputRoot
    PyInstaller dist dir. Portable app lands in <OutputRoot>\FieldRook-Collector.
    Default: <repo>\dist\collector (repo-root dist/ is git-ignored).
.PARAMETER BuildDir
    Scratch dir for the build venv + PyInstaller work files.
    Default: packaging/collector/.build (git-ignored).
.PARAMETER PythonExe
    Host Python used to create the build venv. Default: "python".
.PARAMETER PyInstallerVersion
    Override the pin from requirements-build.txt (experiments only).
.PARAMETER SkipVenv
    Reuse a PyInstaller already on PATH instead of a fresh venv (must equal the pin).
#>
[CmdletBinding()]
param(
    [string]$OutputRoot = "",
    [string]$BuildDir = "",
    [string]$PythonExe = "python",
    [string]$PyInstallerVersion = "",
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"

function Read-Pin {
    param([string]$RequirementsPath, [string]$Override)
    if ($Override -ne "") { return $Override }
    foreach ($line in Get-Content $RequirementsPath) {
        $clean = ($line -split "#", 2)[0].Trim()
        if ($clean -match "^PyInstaller==(.+)$") { return $Matches[1].Trim() }
    }
    throw "No PyInstaller== pin found in $RequirementsPath."
}

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
}

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

$RepoRoot = (Resolve-Path (Join-Path (Join-Path $PSScriptRoot "..") "..")).Path
$SpecPath = Join-Path $PSScriptRoot "FieldRook-Collector.spec"
$RequirementsPath = Join-Path $PSScriptRoot "requirements-build.txt"
$PortableReadme = Join-Path $PSScriptRoot "PORTABLE-README.txt"
$SampleZip = Join-Path $RepoRoot "collector\samples\sample_basic.zip"
if ($OutputRoot -eq "") { $OutputRoot = Join-Path $RepoRoot "dist\collector" }
if ($BuildDir -eq "") { $BuildDir = Join-Path $PSScriptRoot ".build" }
$Pin = Read-Pin $RequirementsPath $PyInstallerVersion

foreach ($required in @($SpecPath, $RequirementsPath, $PortableReadme, $SampleZip)) {
    if (-not (Test-Path $required)) { throw "Required input missing: $required." }
}

Write-Host "== FieldRook-Collector build =="
Write-Host "repo:        $RepoRoot"
Write-Host "pin:         PyInstaller==$Pin"
Write-Host "output root: $OutputRoot"
Write-Host "build dir:   $BuildDir"

New-Item -ItemType Directory -Force -Path $OutputRoot, $BuildDir | Out-Null

if ($SkipVenv) {
    $PyInstallerBin = "pyinstaller"
} else {
    $VenvDir = Join-Path $BuildDir "venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "-- creating build venv ($PythonExe) --"
        Invoke-Checked "venv creation" { & $PythonExe -m venv $VenvDir }
    }
    Write-Host "-- installing pinned toolchain --"
    Invoke-Checked "pip install" { & $VenvPython -m pip install -r $RequirementsPath }
    $PyInstallerBin = Join-Path $VenvDir "Scripts\pyinstaller.exe"
}

$Installed = (& $PyInstallerBin --version | Select-Object -Last 1).Trim()
if ($Installed -ne $Pin) {
    throw "PyInstaller version mismatch: want $Pin, have $Installed."
}
$BuildPythonVersion = (& $PythonExe --version 2>&1 | Select-Object -Last 1).Trim()
Write-Host "toolchain:   $BuildPythonVersion / PyInstaller $Installed"

$WorkPath = Join-Path $BuildDir "work"
Write-Host "-- freezing (one-dir, console) --"
$env:PYTHONHASHSEED = "0"
Invoke-Checked "pyinstaller" {
    & $PyInstallerBin --clean --noconfirm --distpath $OutputRoot --workpath $WorkPath $SpecPath
}

$PortableDir = Join-Path $OutputRoot "FieldRook-Collector"
$Exe = Join-Path $PortableDir "FieldRook-Collector.exe"
if (-not (Test-Path $Exe)) { throw "Build produced no exe at $Exe." }

Copy-Item -Force $PortableReadme (Join-Path $PortableDir "README.txt")

Write-Host "-- smoke: --help --"
$helpOut = & $Exe --help 2>&1
if ($LASTEXITCODE -ne 0) { throw "exe --help exited $LASTEXITCODE." }
Write-Host ($helpOut -join "`n")

Write-Host "-- smoke: validate committed sample --"
$validOut = & $Exe validate $SampleZip 2>&1
if ($LASTEXITCODE -ne 0) { throw "exe validate sample exited $LASTEXITCODE." }
Write-Host ($validOut -join "`n")

Write-Host "-- checksums --"
$sumPath = Join-Path $PortableDir "SHA256SUMS.txt"
$bomPath = Join-Path $PortableDir "BUILD-BOM.txt"
$files = Get-ChildItem -Path $PortableDir -Recurse -File |
    Where-Object { $_.Name -ne "SHA256SUMS.txt" -and $_.Name -ne "BUILD-BOM.txt" } |
    Sort-Object FullName
$sumLines = foreach ($file in $files) {
    $rel = $file.FullName.Substring($PortableDir.Length + 1).Replace("\", "/")
    $hash = Get-Sha256Hex -Path $file.FullName
    "$hash  $rel"
}
$sumLines | Set-Content -Path $sumPath -Encoding utf8
$ExeHash = Get-Sha256Hex -Path $Exe

$GitCommit = "unknown"
$GitBranch = "unknown"
try {
    $GitCommit = (git -C $RepoRoot rev-parse HEAD 2>$null).Trim()
    $GitBranch = (git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null).Trim()
} catch { }

$bom = @(
    "FieldRook-Collector build BOM (M025 ALPHA)",
    "built_at_utc: $([DateTime]::UtcNow.ToString('o'))",
    "git_branch: $GitBranch",
    "git_commit: $GitCommit",
    "build_python: $BuildPythonVersion",
    "pyinstaller: $Installed",
    "spec: packaging/collector/FieldRook-Collector.spec",
    "mode: one-dir, console, upx off, PYTHONHASHSEED=0",
    "portable_dir: FieldRook-Collector ($($files.Count) files + SHA256SUMS.txt + BUILD-BOM.txt)",
    "exe_sha256: $ExeHash  FieldRook-Collector.exe",
    "signing: none (not authorized for M025)"
)
$bom | Set-Content -Path $bomPath -Encoding utf8

Write-Host "== OK =="
Write-Host "exe:  $Exe"
Write-Host "sha256(exe): $ExeHash"
Write-Host "files in portable dir: $($files.Count + 2)"
