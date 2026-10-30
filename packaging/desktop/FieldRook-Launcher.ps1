<# FieldRook desktop launcher (M025 BETA).

Single-instance localhost lifecycle for the frozen desktop build:
env setup -> already-running/port-conflict UX -> start server -> wait for
/api/status -> open browser -> PID-tracked shutdown (server + detached
demo worker via the server's fenced --stop-demo-worker path).

Instance identity comes from /api/status (service + runtime + version):
only a frozen Desktop runtime counts as "already running" — a FieldRook
development server on the port is a port conflict, never "already running".

Runs on Windows PowerShell 5.1+ (ships with Windows; no new dependency).
Start it via FieldRook.bat (handles the execution policy).

Exit codes: 0 ok/ready/stopped, 1 startup or shutdown failure,
2 port conflict, 3 already running (-CheckOnly only).

Parameters:
  -Port       listen port (default $env:FIELDROOK_PORT or 8000)
  -CheckOnly  probe only: report ready/conflict/already-running, start nothing
  -Stop       stop the running instance named by the lock file, start nothing
  -NoBrowser  skip opening the browser after a healthy start
  -WaitSeconds  /api/status wait budget (default 90)
  -ServerExe  override the server executable (default: install's server exe)
  -ServerArgs override extra server args (default: none)
  -WorkDir    override the server working directory
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [switch]$CheckOnly,
    [switch]$Stop,
    [switch]$NoBrowser,
    [int]$WaitSeconds = 90,
    [string]$ServerExe = "",
    [string]$ServerArgs = "",
    [string]$WorkDir = ""
)

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ServerExe)) {
    $ServerExe = Join-Path $InstallDir "server\FieldRook-Server.exe"
}
if ([string]::IsNullOrWhiteSpace($WorkDir)) {
    $WorkDir = Split-Path -Parent $ServerExe
}
if ($Port -eq 0) {
    if ($env:FIELDROOK_PORT -match "^\s*\d+\s*$") { $Port = [int]$env:FIELDROOK_PORT }
    else { $Port = 8000 }
}
if ($Port -lt 1 -or $Port -gt 65535) {
    Write-Error "Invalid port $Port (expected 1-65535)."
    exit 1
}

$LocalAppData = $env:LOCALAPPDATA
if ([string]::IsNullOrWhiteSpace($LocalAppData)) {
    $LocalAppData = Join-Path $HOME ".local\share"
}
$DataDir = Join-Path $LocalAppData "FieldRook"
$LogsDir = Join-Path $DataDir "logs"
$LockFile = Join-Path $DataDir "fieldrook.lock"
$LauncherLog = Join-Path $LogsDir "launcher.log"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LauncherLog -Value $line
    Write-Host $Message
}

function Test-TcpPort([string]$HostName, [int]$TcpPort, [int]$TimeoutMs = 1000) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $TcpPort, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
        $client.EndConnect($iar)
        return $true
    } catch { return $false }
    finally { $client.Close() }
}

function Get-StatusIdentity([int]$StatusPort) {
    # Instance identity of whoever answers /api/status: service + runtime
    # ("desktop" = frozen packaged app, "dev" = source checkout) + version.
    # Anything unreadable degrades to empty strings (never counts as Desktop).
    $empty = @{ Service = ""; Runtime = ""; Version = "" }
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:${StatusPort}/api/status" -TimeoutSec 5
        if ($null -eq $res) { return $empty }
        return @{
            Service = [string]$res.service
            Runtime = [string]$res.runtime
            Version = [string]$res.version
        }
    } catch { return $empty }
}

function Read-Lock {
    if (-not (Test-Path $LockFile)) { return $null }
    try { return (Get-Content $LockFile -Raw | ConvertFrom-Json) }
    catch { return $null }
}

function Get-LockInt($Lock, [string]$Field) {
    # The lock is launcher-written JSON, but a corrupt file must never crash
    # the probe: unparseable fields read as 0 so the lock is cleared as stale.
    try { return [int]$Lock.$Field } catch { return 0 }
}

function Test-PidAlive([int]$ProcessId) {
    try { return $null -ne (Get-Process -Id $ProcessId -ErrorAction Stop) }
    catch { return $false }
}

function Get-ProcessCommandLine([int]$ProcessId) {
    try {
        $proc = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        return [string]$proc.CommandLine
    } catch { return "" }
}

# Probe result: @{ State = 'ready'|'already'|'conflict'; Detail = ... }
function Get-RuntimeState {
    $exeLeaf = Split-Path -Leaf $ServerExe
    $lock = Read-Lock
    if ($null -ne $lock) {
        $lockPort = Get-LockInt $lock "port"
        $lockPid = Get-LockInt $lock "pid"
        if ($lockPort -ne $Port) {
            if ($lockPort -gt 0 -and (Test-PidAlive $lockPid) -and ((Get-ProcessCommandLine $lockPid) -like "*${exeLeaf}*")) {
                return @{ State = "already"; Detail = "FieldRook Desktop is already running on port $lockPort (single instance). Stop it or omit -Port." }
            }
            Remove-Item -Force $LockFile -ErrorAction SilentlyContinue
            Write-Log "Removed stale lock (pid $lockPid, port $lockPort)."
        }
    }
    $tcpOpen = Test-TcpPort "127.0.0.1" $Port
    if ($tcpOpen) {
        $identity = Get-StatusIdentity $Port
        if ($identity.Service -eq "fieldrook-api" -and $identity.Runtime -eq "desktop") {
            $ver = $identity.Version
            if ([string]::IsNullOrWhiteSpace($ver)) { $ver = "unknown" }
            return @{ State = "already"; Detail = "FieldRook is already running on port $Port (Desktop v$ver)." }
        }
        if ($identity.Service -eq "fieldrook-api") {
            $rt = $identity.Runtime
            if ([string]::IsNullOrWhiteSpace($rt)) { $rt = "unknown (older than Desktop identity)" }
            return @{
                State  = "conflict"
                Detail = "Port $Port is in use by a FieldRook development server (runtime '$rt'), not the Desktop app. Stop it or start with -Port <free-port>."
            }
        }
        return @{
            State  = "conflict"
            Detail = "Port $Port is in use by another application (not FieldRook). Stop it or start with -Port <free-port>."
        }
    }
    $stale = Read-Lock
    if ($null -ne $stale) {
        # Port is free: any lock is stale (previous crash/kill). Clear it.
        Remove-Item -Force $LockFile -ErrorAction SilentlyContinue
        Write-Log "Removed stale lock (pid $($stale.pid), port $($stale.port))."
    }
    return @{ State = "ready"; Detail = "Ready: port $Port is free." }
}

function Stop-VerifiedProcess([int]$ProcessId, [string]$MustContain) {
    $cmdline = Get-ProcessCommandLine $ProcessId
    if ([string]::IsNullOrWhiteSpace($cmdline)) {
        Write-Log "pid $ProcessId already exited."
        return
    }
    if ($cmdline -notlike "*$MustContain*") {
        Write-Log "Refusing to kill pid ${ProcessId}: command line does not match '${MustContain}'."
        throw "Kill fence refused pid $ProcessId."
    }
    Stop-Process -Id $ProcessId -Force
    Write-Log "Stopped pid $ProcessId ($MustContain)."
}

function Stop-DemoWorker {
    # Reuses the server's fenced kill path (terminate_verified_worker).
    try {
        $out = & $ServerExe --stop-demo-worker 2>&1 | Out-String
        Write-Log ("demo worker shutdown: " + $out.Trim())
    } catch {
        Write-Log ("demo worker shutdown failed (continuing): " + $_.Exception.Message)
    }
}

function Remove-OwnLock([int]$ServerPid) {
    $lock = Read-Lock
    if ($null -ne $lock -and (Get-LockInt $lock "pid") -eq $ServerPid) {
        Remove-Item -Force $LockFile -ErrorAction SilentlyContinue
    }
}

# ------------------------------------------------------------------ -Stop --
if ($Stop) {
    $lock = Read-Lock
    if ($null -eq $lock) {
        Write-Log "FieldRook is not running (no lock file)."
        exit 0
    }
    $pidToStop = Get-LockInt $lock "pid"
    if (-not (Test-PidAlive $pidToStop)) {
        Remove-Item -Force $LockFile -ErrorAction SilentlyContinue
        Write-Log "Removed stale lock (pid $pidToStop is dead)."
        exit 0
    }
    $exeName = Split-Path -Leaf $ServerExe
    try {
        Stop-VerifiedProcess $pidToStop $exeName
    } catch {
        Write-Error $_.Exception.Message
        exit 1
    }
    Stop-DemoWorker
    Remove-OwnLock $pidToStop
    Write-Log "FieldRook stopped."
    exit 0
}

# -------------------------------------------------------------- -CheckOnly --
$state = Get-RuntimeState
if ($CheckOnly) {
    Write-Log ("CheckOnly: " + $state.Detail)
    if ($state.State -eq "ready") { exit 0 }
    if ($state.State -eq "already") { exit 3 }
    exit 2
}

# ------------------------------------------------------------------- start --
if ($state.State -eq "already") {
    Write-Log ($state.Detail + " Opening the browser instead of starting a second copy.")
    Start-Process "http://127.0.0.1:${Port}/"
    exit 0
}
if ($state.State -eq "conflict") {
    Write-Error $state.Detail
    exit 2
}
if (-not (Test-Path $ServerExe)) {
    Write-Error "Server executable not found: $ServerExe"
    exit 1
}

# Env setup. Explicit operator values always win; otherwise the desktop
# defaults point at the per-user data dir — never at a dev checkout DB.
$env:FIELDROOK_PORT = "$Port"
if ([string]::IsNullOrWhiteSpace($env:FIELDROOK_DB_PATH)) {
    $env:FIELDROOK_DB_PATH = Join-Path $DataDir "fieldrook.db"
}
if ([string]::IsNullOrWhiteSpace($env:FIELDROOK_DEMO_STATE)) {
    $env:FIELDROOK_DEMO_STATE = Join-Path $DataDir "demo-state"
}
Write-Log "Starting FieldRook (port $Port, data $DataDir)."
Write-Log "DB: $($env:FIELDROOK_DB_PATH)"

$serverOut = Join-Path $LogsDir "server.out.log"
$serverErr = Join-Path $LogsDir "server.err.log"
$startArgs = @{
    FilePath               = $ServerExe
    WorkingDirectory       = $WorkDir
    PassThru               = $true
    RedirectStandardOutput = $serverOut
    RedirectStandardError  = $serverErr
}
if (-not [string]::IsNullOrWhiteSpace($ServerArgs)) {
    $startArgs["ArgumentList"] = $ServerArgs
}
$server = Start-Process @startArgs
$serverPid = $server.Id
Write-Log "Server starting (pid $serverPid)."
@{ pid = $serverPid; port = $Port; service = "fieldrook-api" } |
    ConvertTo-Json | Set-Content -Path $LockFile

$exeLeaf = Split-Path -Leaf $ServerExe
try {
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    $healthy = $false
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-PidAlive $serverPid)) { break }
        if ((Get-StatusIdentity $Port).Service -eq "fieldrook-api") { $healthy = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $healthy) {
        Write-Log "Server did not become healthy within ${WaitSeconds}s (see $serverErr)."
        if (Test-Path $serverErr) {
            Write-Log "--- server.err.log (tail) ---"
            Get-Content $serverErr -Tail 30 | ForEach-Object { Write-Log $_ }
        }
        throw "Server failed to start."
    }
    Write-Log "FieldRook is healthy at http://127.0.0.1:${Port}/"
    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:${Port}/"
        Write-Log "Browser opened. Close this window (Ctrl+C) to stop FieldRook."
    } else {
        Write-Log "Running headless (-NoBrowser). Press Ctrl+C to stop."
    }
    try {
        Wait-Process -Id $serverPid
        Write-Log "Server process exited on its own; shutting down."
    } catch {
        # Wait-Process throws when WE are interrupted (Ctrl+C) — that is the
        # normal stop path and falls through to the finally shutdown below.
        Write-Log "Stop requested; shutting down."
    }
} finally {
    if (Test-PidAlive $serverPid) {
        try { Stop-VerifiedProcess $serverPid $exeLeaf }
        catch { Write-Log ("server stop failed: " + $_.Exception.Message) }
    }
    Stop-DemoWorker
    Remove-OwnLock $serverPid
    Write-Log "FieldRook stopped."
}
