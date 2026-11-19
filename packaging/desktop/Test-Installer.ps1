<# M039: acceptance of a real installer in a disposable, isolated path.
Requires no admin. WILL install and then uninstall FieldRook in the current
user's Windows Apps/Start Menu registry. Refuses existing FieldRook installs.
Does not close or modify portable instances. Does NOT delete case data.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InstallerPath,
    [Parameter(Mandatory)][string]$Version,
    [string]$TestRoot = ""
)
$ErrorActionPreference = "Stop"
$InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
if (-not $TestRoot) {
    $TestRoot = Join-Path (Split-Path -Parent $InstallerPath) "_m039_acceptance"
}
$TestRoot = [IO.Path]::GetFullPath($TestRoot)
$installDir = Join-Path $TestRoot "installed"
$local = Join-Path $TestRoot "local-app-data"
$marker = Join-Path $local "FieldRook\keep-this-case.txt"
$logInstall = Join-Path $TestRoot "install.log"
$logReinstall = Join-Path $TestRoot "reinstall.log"
$logUninstall = Join-Path $TestRoot "uninstall.log"
$regPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8A7EAFA3-3BD4-4DA1-82F3-885D214F92D1}_is1'
$shortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\FieldRook.lnk"
if (Test-Path -LiteralPath $regPath) { throw "A FieldRook installer registration exists. Refusing to replace it." }
if (Test-Path -LiteralPath $installDir) { throw "Acceptance install directory already exists: $installDir" }

$baseline = @(Get-CimInstance Win32_Process -Filter "Name = 'FieldRook.exe'" |
    Select-Object -ExpandProperty ProcessId)
$cleanupOwned = $false
$passed = $false

function Invoke-Setup {
    param([string]$Executable,[string]$LogFile)
    $args = @(
        "/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
        "/NOCLOSEAPPLICATIONS",
        ("/DIR=" + [char]34 + $installDir + [char]34),
        ("/LOG=" + [char]34 + $LogFile + [char]34)
    )
    $p = Start-Process -FilePath $Executable -ArgumentList $args -PassThru -Wait
    if ($p.ExitCode -ne 0) {
        throw "Setup exit $($p.ExitCode). Inspect $LogFile."
    }
}
function Read-OwnedRegistration {
    if (-not (Test-Path -LiteralPath $regPath)) {throw "Expected uninstall entry missing"}
    $value = Get-ItemProperty -LiteralPath $regPath
    if ([IO.Path]::GetFullPath($value.InstallLocation).TrimEnd('\') -ine
        [IO.Path]::GetFullPath($installDir).TrimEnd('\')) {
        throw "Uninstall entry points outside the acceptance directory; refusing to touch it."
    }
    return $value
}
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $local "FieldRook") | Out-Null
    Set-Content -LiteralPath $marker -Value "M039 sentinel: preserve user data"
    Write-Host "M039 installing $Version to disposable path $installDir"
    Invoke-Setup -Executable $InstallerPath -LogFile $logInstall
    $installed = Read-OwnedRegistration
    $cleanupOwned = $true
    $exe = Join-Path $installDir "FieldRook.exe"
    $server = Join-Path $installDir "server\FieldRook-Server.exe"
    $worker = Join-Path $installDir "server\_internal\demo-worker\fieldrook-demo-worker.exe"
    $frontend = Join-Path $installDir "server\_internal\frontend-dist\index.html"
    foreach ($path in @($exe,$server,$worker,$frontend,$shortcut)) {
        if (-not (Test-Path -LiteralPath $path)) {throw "Missing installed payload or shortcut: $path"}
    }
    $productVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($exe).ProductVersion
    if (-not $productVersion.StartsWith($Version,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Wrong installed app version: $productVersion"
    }
    if ($installed.DisplayVersion -ne $Version) {throw "Wrong registered version $($installed.DisplayVersion)"}
    Write-Host "INSTALL_PASS version=$productVersion StartMenu=true UninstallEntry=true"

    # Headless native lifecycle must use a distinct port and data, never touch the
    # already running portable rc.2 window or its database / lock.
    $originalLocal = $env:LOCALAPPDATA
    $originalPort = $env:FIELDROOK_PORT
    $originalDb = $env:FIELDROOK_DB_PATH
    $originalDemo = $env:FIELDROOK_DEMO_STATE
    try {
        $env:LOCALAPPDATA = $local
        $env:FIELDROOK_PORT = "8199"
        $env:FIELDROOK_DB_PATH = Join-Path $local "FieldRook\smoke.db"
        $env:FIELDROOK_DEMO_STATE = Join-Path $local "FieldRook\demo"
        $p = Start-Process -FilePath $exe -ArgumentList @("--smoke","--port","8199","--wait-seconds","35") -PassThru -Wait
        if ($p.ExitCode -ne 0) {throw "Installed native smoke exit $($p.ExitCode)"}
    }
    finally {
        $env:LOCALAPPDATA = $originalLocal
        $env:FIELDROOK_PORT = $originalPort
        $env:FIELDROOK_DB_PATH = $originalDb
        $env:FIELDROOK_DEMO_STATE = $originalDemo
    }
    Write-Host "INSTALLED_NATIVE_SMOKE_PASS"

    Invoke-Setup -Executable $InstallerPath -LogFile $logReinstall
    $null = Read-OwnedRegistration
    if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $marker)) {
        throw "Reinstall damaged executable or isolated case marker."
    }
    Write-Host "IN_PLACE_REINSTALL_PASS"

    $uninstaller = Join-Path $installDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $uninstaller)) {throw "Uninstaller not present"}
    $args = @("/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART",
        ("/LOG=" + [char]34 + $logUninstall + [char]34))
    $p = Start-Process -FilePath $uninstaller -ArgumentList $args -PassThru -Wait
    if ($p.ExitCode -ne 0) {throw "Uninstaller failed with exit $($p.ExitCode)"}
    if ((Test-Path -LiteralPath $regPath) -or
        (Test-Path -LiteralPath $shortcut) -or
        (Test-Path -LiteralPath $exe)) {throw "Uninstall left files, shortcut or registration behind"}
    if (-not (Test-Path -LiteralPath $marker)) {throw "User data marker was deleted"}
    foreach ($baselinePid in $baseline) {
        if (-not (Get-Process -Id $baselinePid -ErrorAction SilentlyContinue)) {
            throw "Previously running FieldRook PID $baselinePid disappeared; verify it was not interrupted"
        }
    }
    $cleanupOwned = $false
    $passed = $true
    Write-Host "UNINSTALL_AND_DATA_RETENTION_PASS"
    Write-Host "PORTABLE_INSTANCES_UNTOUCHED=$($baseline.Count)"
    Write-Host "M039_ACCEPTANCE_PASS"
}
finally {
    # On an unexpected test error, only attempt cleanup if registration STILL
    # points to the disposable test directory. Never uninstall a pre-existing app.
    if ($cleanupOwned -and (Test-Path -LiteralPath $regPath)) {
        try {
            $v = Read-OwnedRegistration
            $uninstaller = Join-Path $installDir "unins000.exe"
            if (Test-Path -LiteralPath $uninstaller) {
                Write-Host "Cleaning up test-owned installation after failed acceptance..."
                $p = Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART") -PassThru -Wait
                Write-Host "CLEANUP_EXIT=$($p.ExitCode)"
            }
        }
        catch {Write-Warning "Manual cleanup of test installation may be needed: $_"}
    }
    if (-not $passed) {Write-Warning "M039 acceptance did not finish cleanly; inspect test root $TestRoot"}
}
