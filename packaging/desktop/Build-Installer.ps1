<# M038: make a real, per-user installer from a matching, committed bundle.

Run build.ps1 then Build-Shell.ps1 first. Build-Installer refuses to silently
wrap an old or partially assembled server. Inno Setup 6 compiler is required
on the BUILD computer only; end users need no build tools.
#>
[CmdletBinding()]
param(
    [string]$OutDir = "",
    [string]$BundleDir = "",
    [string]$InnoCompiler = ""
)
$ErrorActionPreference = "Stop"
$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PackagingDir)
$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim().Split("`n")[0].Trim()
if (-not $Version) { throw "VERSION is missing or empty." }
if (-not $OutDir) { $OutDir = Join-Path $PackagingDir "dist\m038-local" }
$OutDir = [IO.Path]::GetFullPath($OutDir)
if (-not $BundleDir) { $BundleDir = Join-Path $OutDir ("FieldRook-" + $Version) }
$BundleDir = [IO.Path]::GetFullPath($BundleDir)

$Shell = Join-Path $BundleDir "FieldRook.exe"
$Server = Join-Path $BundleDir "server\FieldRook-Server.exe"
$Worker = Join-Path $BundleDir "server\_internal\demo-worker\fieldrook-demo-worker.exe"
$WebApp = Join-Path $BundleDir "server\_internal\frontend-dist\index.html"
$Readme = Join-Path $BundleDir "README.txt"
$Zip = Join-Path $OutDir ("FieldRook-" + $Version + ".zip")
$Bom = Join-Path $OutDir "BOM.txt"
foreach ($file in @($Shell, $Server, $Worker, $WebApp, $Readme, $Zip, $Bom)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Refusing incomplete installation bundle: missing $file"
    }
}
if ((Get-Item $Shell).Length -lt 1000000 -or (Get-Item $Server).Length -lt 100000) {
    throw "Unexpectedly small executable; refusing to package the bundle."
}

$Head = (git -C $RepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot read Git HEAD." }
$Dirty = @(git -C $RepoRoot status --porcelain=v1)
if ($LASTEXITCODE -ne 0 -or $Dirty.Count -gt 0) {
    throw "Source checkout is dirty; commit and review before building an installer."
}
$BomText = Get-Content -LiteralPath $Bom -Raw
if ($BomText -notmatch "(?m)^git commit:\s+$([regex]::Escape($Head))\s*$") {
    throw "BOM source commit does not match the current checkout ($Head). Rebuild the bundle."
}
$ShellVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($Shell).ProductVersion
if (-not $ShellVersion -or -not $ShellVersion.StartsWith($Version, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Shell ProductVersion '$ShellVersion' differs from VERSION '$Version'."
}
$ServerVersion = (& $Server --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $ServerVersion -ne $Version) {
    throw "Frozen server version '$ServerVersion' differs from VERSION '$Version'."
}

if (-not $InnoCompiler) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $InnoCompiler = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
}
if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler -PathType Leaf)) {
    throw "Inno Setup 6 ISCC.exe not found. Install it on the build PC or pass -InnoCompiler."
}

# Inno's Windows file version must contain four numeric components.
$match = [regex]::Match($Version, "^(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$")
if (-not $match.Success) { throw "Unsupported VERSION '$Version' for installer file version." }
$revision = if ($match.Groups[4].Success) { $match.Groups[4].Value } else { "0" }
$numeric = "$($match.Groups[1].Value).$($match.Groups[2].Value).$($match.Groups[3].Value).$revision"

$Script = Join-Path $PackagingDir "FieldRook.iss"
$Icon = Join-Path $RepoRoot "native-shell\src\FieldRook\Assets\FieldRook.ico"
if (-not (Test-Path -LiteralPath $Script) -or -not (Test-Path -LiteralPath $Icon)) {
    throw "Inno source or application icon is missing."
}
Write-Host "Compiling FieldRook $Version Windows setup from commit $Head"
Write-Host "Bundle: $BundleDir"
& $InnoCompiler "/Q" "/DPackageVersion=$Version" "/DNumericVersion=$numeric" `
    "/DBundleDir=$BundleDir" "/DOutputDir=$OutDir" "/DIconPath=$Icon" $Script
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compiler failed (exit $LASTEXITCODE)." }

$Installer = Join-Path $OutDir ("FieldRook-Setup-" + $Version + ".exe")
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "Installer executable missing: $Installer"
}
# Use the same .NET SHA256 implementation as build.ps1 and Build-Shell.ps1.
# Windows PowerShell 5.1 may inherit PowerShell 7's PSModulePath, making
# Get-FileHash auto-import fail even on a supported Windows build machine.
function Get-Sha256Hex {
    param([string]$Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { $bytes = $sha.ComputeHash($stream) }
        finally { $stream.Dispose() }
    }
    finally { $sha.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
}
$hash = Get-Sha256Hex -Path $Installer
$zipHash = Get-Sha256Hex -Path $Zip
@(
    "$hash  $(Split-Path -Leaf $Installer)"
    "$zipHash  $(Split-Path -Leaf $Zip)"
) | Set-Content -Encoding ASCII (Join-Path $OutDir "INSTALLER_SHA256.txt")
@"
FieldRook $Version — LOCAL UNSIGNED INSTALLER CANDIDATE
Source Git commit: $Head
Built: $(Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
Source checkout: clean at installer compilation
Bundle: $BundleDir
Installer: $Installer
Installer SHA256: $hash
Portable zip SHA256: $zipHash
Signing: NOT SIGNED; Windows SmartScreen may warn
WebView2 Runtime: required on installed machine
Install scope: per-user, no admin
User data: %LOCALAPPDATA%\FieldRook (not removed on uninstall)
Not a release: no publication, clean-machine or upgrade acceptance yet
"@ | Set-Content -Encoding UTF8 (Join-Path $OutDir "INSTALLER_BUILD.txt")

Write-Host "INSTALLER OK: $Installer"
Write-Host "SHA256: $hash"
