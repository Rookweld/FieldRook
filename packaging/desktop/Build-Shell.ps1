<# FieldRook native-shell build (M026 ALPHA).

Publishes the WPF + WebView2 shell (native-shell/) and integrates it into
the portable desktop layout produced by build.ps1:

  dist/FieldRook-<VERSION>/
    FieldRook.exe            <- the shell (this script)
    server/                  <- frozen backend incl. UI (build.ps1)
    FieldRook.bat / FieldRook-Launcher.ps1 / README.txt

Usage (from the repo root):
  powershell -ExecutionPolicy Bypass -File packaging\desktop\Build-Shell.ps1
  powershell -ExecutionPolicy Bypass -File packaging\desktop\Build-Shell.ps1 -PublishMode FrameworkDependent

Version comes from the VERSION file (single source); assembly metadata is
stamped from it. Requires: .NET 10 SDK. No signing (not authorized).

Publish modes (contract 6 asks ALPHA to justify the choice):
  SelfContained (default): zero prerequisites on the target except the
    WebView2 Runtime (already required by contract; the shell shows install
    guidance when it is missing). Matches the M025 "no toolchain on the
    target" philosophy. Larger (~70-120 MB), single file next to server/.
  FrameworkDependent: small download, but the target needs the .NET 10
    Desktop Runtime x64 installed (per-user install is enough, no admin).
#>
[CmdletBinding()]
param(
    [string]$OutDir = "",
    [ValidateSet("SelfContained", "FrameworkDependent")]
    [string]$PublishMode = "SelfContained",
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PackagingDir)
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $PackagingDir "dist" }
$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim().Split("`n")[0].Trim()
if ([string]::IsNullOrWhiteSpace($Version)) { throw "VERSION file is empty." }

$ShellProject = Join-Path $RepoRoot "native-shell\src\FieldRook\FieldRook.csproj"
if (-not (Test-Path $ShellProject)) { throw "Shell project not found: $ShellProject" }

Write-Host "FieldRook shell build $Version ($PublishMode, $Configuration)"

# ------------------------------------------------------------- prerequisites
$sdks = (& dotnet --list-sdks 2>$null) -join "`n"
if ($sdks -notmatch "(?m)^10\.") { throw ".NET 10 SDK required (dotnet --list-sdks shows none)." }
$sdkLine = ($sdks -split "`n" | Where-Object { $_ -match "^10\." } | Select-Object -First 1).Trim()
Write-Host "SDK: $sdkLine"

$webview2Pin = (Select-String -Path $ShellProject -Pattern 'Microsoft\.Web\.WebView2" Version="([^"]+)"').Matches[0].Groups[1].Value
Write-Host "WebView2 SDK pin: $webview2Pin"

# ----------------------------------------------------------------- publish --
$WorkRoot = Join-Path $OutDir "_work"
$PublishDir = Join-Path $WorkRoot "shell-publish"
if (Test-Path $PublishDir) { Remove-Item -Recurse -Force $PublishDir }

$selfContained = $PublishMode -eq "SelfContained"
& dotnet publish $ShellProject -c $Configuration -r win-x64 `
    --self-contained:$($selfContained.ToString().ToLower()) `
    /p:Version=$Version /p:InformationalVersion=$Version `
    /p:PublishSingleFile=true /p:IncludeNativeLibrariesForSelfExtract=true `
    -o $PublishDir
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed." }

$shellExe = Join-Path $PublishDir "FieldRook.exe"
if (-not (Test-Path $shellExe)) { throw "FieldRook.exe missing after publish." }
$shellBytes = (Get-Item $shellExe).Length
Write-Host ("Published: {0} ({1:N0} bytes)" -f $shellExe, $shellBytes)

# Sanity: the stamped version must equal VERSION (ZETA verifies this).
$asmVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($shellExe).ProductVersion
if ($asmVersion -notlike "$Version*") { throw "Assembly version '$asmVersion' does not match VERSION '$Version'." }
Write-Host "Assembly version: $asmVersion (matches VERSION)."

# --------------------------------------------------------------- integrate --
$AssembleDir = Join-Path $OutDir ("FieldRook-" + $Version)
if (-not (Test-Path (Join-Path $AssembleDir "server\FieldRook-Server.exe"))) {
    Write-Host ""
    Write-Host "Publish OK, but no desktop bundle found at $AssembleDir."
    Write-Host "Run packaging\desktop\build.ps1 first, then re-run this script to integrate."
    Write-Host "Shell output left at: $PublishDir"
    exit 0
}

Copy-Item $shellExe (Join-Path $AssembleDir "FieldRook.exe") -Force
# Single-file publish may still emit a .pdb + host config next to the exe;
# ship only the exe: the bundle stays exactly {FieldRook.exe, server/, ...}.
Write-Host "Integrated: $(Join-Path $AssembleDir 'FieldRook.exe')"

function Get-Sha256Hex {
    param([string]$Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { $bytes = $sha.ComputeHash($stream) }
        finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace("-", "").ToLower()
}

$shellHash = Get-Sha256Hex -Path (Join-Path $AssembleDir "FieldRook.exe")
$sumsPath = Join-Path $OutDir "SHA256SUMS.txt"
$sums = @()
if (Test-Path $sumsPath) {
    $sums = @(Get-Content $sumsPath | Where-Object { $_ -notmatch "FieldRook\.exe$" })
}
$sums += "$shellHash  FieldRook.exe"
$sums | Set-Content $sumsPath

$runtimeReq = if ($selfContained) {
    "WebView2 Runtime only (evergreen); NO .NET runtime required (self-contained)."
} else {
    "WebView2 Runtime + .NET 10 Desktop Runtime x64 (per-user install is enough)."
}
$bomPath = Join-Path $OutDir "BOM.txt"
@"

shell provenance (M026 ALPHA):
  dotnet sdk:        $sdkLine
  webview2 sdk pin:  $webview2Pin (NuGet)
  publish mode:      $PublishMode (win-x64, single file)
  required runtimes: $runtimeReq
  shell exe sha256:  $shellHash
"@ | Add-Content $bomPath

$zipPath = Join-Path $OutDir ("FieldRook-" + $Version + ".zip")
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path $AssembleDir -DestinationPath $zipPath
Write-Host "Archive refreshed: $zipPath"
Write-Host ""
Write-Host "Shell build OK: $(Join-Path $AssembleDir 'FieldRook.exe')"
