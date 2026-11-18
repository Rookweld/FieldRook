<# M038 one-command local candidate builder.
Freeze server + frontend -> publish WPF -> create per-user Setup.exe.
Source must be committed and clean. Only produces unsigned LOCAL candidates.
#>
[CmdletBinding()]
param(
    [string]$OutDir = "",
    [switch]$SkipFrontend,
    [string]$PythonExe = "",
    [string]$InnoCompiler = ""
)
$ErrorActionPreference = "Stop"
$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutDir) { $OutDir = Join-Path $PackagingDir "dist\m038-local" }
$OutDir = [IO.Path]::GetFullPath($OutDir)
Write-Host "M038: assembling a clean local FieldRook release candidate."
Write-Host "Destination: $OutDir"

& (Join-Path $PackagingDir "build.ps1") -OutDir $OutDir -SkipFrontend:$SkipFrontend -PythonExe $PythonExe
if (-not $?) { throw "Freezing backend/frontend failed." }

& (Join-Path $PackagingDir "Build-Shell.ps1") -OutDir $OutDir
if (-not $?) { throw "Publishing native shell failed." }

& (Join-Path $PackagingDir "Build-Installer.ps1") -OutDir $OutDir -InnoCompiler $InnoCompiler
if (-not $?) { throw "Compiling Windows Setup failed." }

Write-Host ""
Write-Host "M038 LOCAL CANDIDATE COMPLETE."
Write-Host "Installer and portable ZIP: $OutDir"
Write-Host "Do not publish until clean-machine, upgrade and antivirus acceptance."
