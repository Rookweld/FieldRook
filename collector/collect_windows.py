"""Read-only Windows collectors (contracts v1, section 2).

Six collection categories — ``services``, ``os``, ``events``,
``network``, ``tasks``, ``procs`` — built from stdlib plus FIXED
PowerShell commands only (copies of the backend allowlisted scripts;
no interpolation except validated integers/service names). Nothing here
changes system state. No active tests (no ``Resolve-DnsName``).

Consent: :data:`CATEGORIES` carries per-category consent display text
plus privilege flags (``current_user_readonly`` |
``elevated_recommended``). :func:`collect_all` refuses to run until the
caller passes ``consent_ack=True`` (the technician has shown
:func:`format_consent_screen` and the user agreed).

Privacy: every payload is redacted with ``redact_import.redact_data``
before it leaves this module; the local hostname is hashed (D8) and raw
occurrences become ``[host <hint>]``; full command lines are never
collected (process queries select ``ExecutablePath`` only) and any
``command_line``-like key found downstream is dropped. Each entry's
``data.provenance.redaction_count`` records the substitution count (D1b).

``fixture=True`` returns deterministic realistic synthetic data for
offline tests and sample packages (``source_suffix="fixture"``).
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from .manifest import utc_now_iso
from .redact_import import build_identity, redact_data

__all__ = [
    "CATEGORIES",
    "FIXED_COMMANDS",
    "CollectionResult",
    "collect_all",
    "format_consent_screen",
    "manifest_os_info",
    "powershell_available",
    "validate_service_name",
]

# ---------------------------------------------------------------------------
# Fixed PowerShell surface (read-only; copies of backend allowlisted scripts)
# ---------------------------------------------------------------------------

FIXED_COMMANDS = (
    "Get-Service",
    "Get-CimInstance Win32_Service",
    "Get-CimInstance Win32_OperatingSystem",
    "Get-NetAdapter",
    "Get-NetIPAddress",
    "Get-DnsClientServerAddress",
    "Get-NetTCPConnection Established",
    "Get-WinEvent -LogName System",
    "Get-ScheduledTask",
    "Get-ScheduledTaskInfo",
    "Get-CimInstance Win32_Process",
    "Get-Service/Dependencies",
)

_LIST_SCRIPT = (
    "Get-Service | Select-Object Name,DisplayName,Status | ConvertTo-Json -Compress -Depth 3"
)
_STATUS_SCRIPT_TEMPLATE = (
    "Get-Service -Name '{name}' "
    "| Select-Object Name,DisplayName,Status,ServiceType | ConvertTo-Json -Compress -Depth 3"
)
_STARTUP_SCRIPT_TEMPLATE = (
    "Get-CimInstance -ClassName Win32_Service -Filter \"Name='{name}'\" "
    "| Select-Object Name,StartMode,State,StartName | ConvertTo-Json -Compress -Depth 3"
)
_DEPENDENCIES_TEMPLATE = (
    "$s = Get-Service -Name '{name}' -ErrorAction Stop; "
    "@{required = @($s.ServicesDependedOn | Select-Object -ExpandProperty Name); "
    "dependent = @($s.DependentServices | Select-Object -ExpandProperty Name)} "
    "| ConvertTo-Json -Compress -Depth 3"
)
_OS_SCRIPT = (
    "Get-CimInstance -ClassName Win32_OperatingSystem "
    "| Select-Object Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime,WindowsDirectory "
    "| ConvertTo-Json -Compress -Depth 3"
)
_ADAPTERS_SCRIPT = (
    "Get-NetAdapter "
    "| Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress,InterfaceIndex "
    "| ConvertTo-Json -Compress -Depth 3"
)
_IP_SCRIPT = (
    "Get-NetIPAddress "
    "| Select-Object InterfaceAlias,IPAddress,PrefixLength,AddressFamily,PrefixOrigin,SuffixOrigin "
    "| ConvertTo-Json -Compress -Depth 3"
)
_DNS_SCRIPT = (
    "Get-DnsClientServerAddress "
    "| Select-Object InterfaceAlias,ServerAddresses "
    "| ConvertTo-Json -Compress -Depth 3"
)
_CONNECTIONS_SCRIPT = (
    "Get-NetTCPConnection -State Established "
    "| Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess "
    "| ConvertTo-Json -Compress -Depth 3"
)
_EVENTS_SCRIPT = (
    "Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2,3; "
    "StartTime=(Get-Date).AddHours(-24)} -MaxEvents 200 -ErrorAction SilentlyContinue "
    "| Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message "
    "| ConvertTo-Json -Compress -Depth 3"
)
_TASKS_SCRIPT = (
    'Get-ScheduledTask | ForEach-Object { $t = $_; [PSCustomObject]@{ '
    'TaskName = $t.TaskName; TaskPath = $t.TaskPath; State = $t.State.ToString(); '
    'Author = $t.Author; Description = $t.Description; '
    'Principal = [PSCustomObject]@{ UserId = $t.Principal.UserId; '
    'LogonType = [int]$t.Principal.LogonType; RunLevel = [int]$t.Principal.RunLevel }; '
    'Triggers = @($t.Triggers | ForEach-Object { [PSCustomObject]@{ '
    'Type = $_.CimClass.CimClassName; Enabled = $_.Enabled; '
    'StartBoundary = $_.StartBoundary; EndBoundary = $_.EndBoundary; '
    'RepetitionInterval = "$($_.Repetition.Interval)"; '
    'RepetitionDuration = "$($_.Repetition.Duration)"; '
    'DaysInterval = $_.DaysInterval; WeeksInterval = $_.WeeksInterval } }); '
    'Actions = @($t.Actions | ForEach-Object { [PSCustomObject]@{ Execute = $_.Execute; '
    'Arguments = $_.Arguments; WorkingDirectory = $_.WorkingDirectory } }) } } '
    '| ConvertTo-Json -Compress -Depth 5'
)
_TASK_INFO_SCRIPT = (
    "Get-ScheduledTask | Get-ScheduledTaskInfo "
    "| Select-Object TaskName,TaskPath,LastRunTime,LastTaskResult,NextRunTime,NumberOfMissedRuns "
    "| ConvertTo-Json -Compress -Depth 3"
)
# Collector-native list (backend only queries by name/pid): top-N by memory,
# executable path only — CommandLine is never selected.
_PROC_LIST_TEMPLATE = (
    "Get-CimInstance -ClassName Win32_Process "
    "| Select-Object ProcessId,Name,ExecutablePath,CreationDate,WorkingSetSize "
    "| Sort-Object WorkingSetSize -Descending | Select-Object -First {limit} "
    "| ConvertTo-Json -Compress -Depth 3"
)

_SERVICE_NAME_RE = re.compile(r"[A-Za-z0-9_.\-]{1,64}")
MAX_ARGUMENT_CHARS = 300
MAX_DESCRIPTION_CHARS = 500
MAX_EVENT_MESSAGE_CHARS = 500

# ---------------------------------------------------------------------------
# Consent metadata + privilege flags (shown to the user before collection)
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, dict[str, Any]] = {
    "services": {
        "label": "Windows services",
        "evidence": ["service_list", "service_details"],
        "description": "Service names, display names, statuses, startup types.",
        "consent": "Read the list of Windows services and their status (names and states only).",
        "privilege": "current_user_readonly",
        "powershell": ["Get-Service", "Get-CimInstance Win32_Service"],
        "minimization": "No file contents, no credentials, no command lines.",
    },
    "os": {
        "label": "Operating system",
        "evidence": ["os_info"],
        "description": "OS edition, version, build, architecture, last boot time.",
        "consent": "Read basic operating-system information (edition, version, boot time).",
        "privilege": "current_user_readonly",
        "powershell": ["Get-CimInstance Win32_OperatingSystem"],
        "minimization": "Hostnames are hashed; no user files are read.",
    },
    "events": {
        "label": "System event log (recent errors/warnings)",
        "evidence": ["event_log"],
        "description": "Most recent System log error/warning entries (24h, capped).",
        "consent": "Read recent System event-log errors and warnings (last 24 hours, capped sample).",
        "privilege": "elevated_recommended",
        "privilege_note": "Some providers are truncated without elevation; collection still works as current user.",
        "powershell": ["Get-WinEvent -LogName System"],
        "minimization": "Messages truncated to 500 chars; secrets, emails and usernames redacted.",
    },
    "network": {
        "label": "Network configuration",
        "evidence": ["net_adapters", "ip_config", "dns_config", "connections"],
        "description": "Adapters, IP addresses, DNS servers, established connections sample.",
        "consent": "Read network configuration and a sample of established connections (addresses/ports only).",
        "privilege": "current_user_readonly",
        "powershell": [
            "Get-NetAdapter",
            "Get-NetIPAddress",
            "Get-DnsClientServerAddress",
            "Get-NetTCPConnection Established",
        ],
        "minimization": "No packet contents; connection sample is bounded.",
    },
    "tasks": {
        "label": "Scheduled tasks",
        "evidence": ["scheduled_tasks"],
        "description": "Task definitions (triggers, actions, principals) + last-run results.",
        "consent": "Read scheduled-task definitions and last-run results (Microsoft tasks excluded by default).",
        "privilege": "elevated_recommended",
        "privilege_note": "Some task definitions are hidden without elevation; visible tasks are still collected.",
        "powershell": ["Get-ScheduledTask", "Get-ScheduledTaskInfo"],
        "minimization": "Arguments truncated to 300 chars; secrets and usernames redacted.",
    },
    "procs": {
        "label": "Running processes (top by memory)",
        "evidence": ["process_info"],
        "description": "Top processes: PID, name, executable path, start time, memory.",
        "consent": "Read the list of top running processes (name, executable path and memory only).",
        "privilege": "current_user_readonly",
        "powershell": ["Get-CimInstance Win32_Process"],
        "minimization": "Full command lines are NEVER collected — executable path only.",
    },
}


def validate_service_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not _SERVICE_NAME_RE.fullmatch(cleaned):
        raise ValueError(
            f"Invalid service name {name!r}: use 1-64 characters of A-Z a-z 0-9 _ . -"
        )
    return cleaned


def format_consent_screen(categories: list[str] | None = None) -> str:
    """Render the per-category consent display for the technician."""
    keys = list(categories) if categories else sorted(CATEGORIES)
    lines = [
        "FieldRook collector — read-only collection. Nothing will be changed.",
        "The following will be read on this computer:",
        "",
    ]
    for key in keys:
        meta = CATEGORIES[key]
        lines.append(f"- {meta['label']} [{meta['privilege']}]\n  {meta['consent']}")
    lines += [
        "",
        "Privacy: secrets, emails, usernames and hostnames are redacted on this",
        "computer before the package is written. The hostname is stored only as",
        "a hash plus your label. Full command lines are never collected.",
    ]
    return "\n".join(lines)


class DiagnosticCommandError(RuntimeError):
    def __init__(self, message: str, source: str) -> None:
        super().__init__(message)
        self.source = source


def powershell_available() -> bool:
    return os.name == "nt" and shutil.which("powershell") is not None


def _run_powershell(script: str, source: str, timeout_s: float) -> str:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise DiagnosticCommandError("PowerShell executable was not found.", source) from exc
    except subprocess.TimeoutExpired as exc:
        raise DiagnosticCommandError(f"Command timed out after {timeout_s:g}s.", source) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip().replace(
            "\n", " "
        )[:300]
        raise DiagnosticCommandError(
            f"PowerShell exit code {completed.returncode}: {detail}", source
        )
    return (completed.stdout or "").strip()


def _as_dict_list(payload: str, source: str) -> list[dict]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DiagnosticCommandError(
            f"Could not parse command output as JSON: {exc}", source
        ) from exc
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    return []


_SERVICE_STATUS_NAMES = {
    1: "Stopped", 2: "StartPending", 3: "StopPending", 4: "Running",
    5: "ContinuePending", 6: "PausePending", 7: "Paused",
}


def _status_name(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int) and value in _SERVICE_STATUS_NAMES:
        return _SERVICE_STATUS_NAMES[value]
    text = str(value or "").strip()
    if text.isdigit() and int(text) in _SERVICE_STATUS_NAMES:
        return _SERVICE_STATUS_NAMES[int(text)]
    return text or "Unknown"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…[truncated]"


def _as_list(value: object) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


# ---------------------------------------------------------------------------
# Live collectors (each returns (payload, error); payload is pre-redaction)
# ---------------------------------------------------------------------------

def _live_services(timeout_s: float, limit: int) -> tuple[dict, str | None]:
    try:
        payload = _run_powershell(_LIST_SCRIPT, "powershell:Get-Service", timeout_s)
        services = []
        for entry in _as_dict_list(payload, "powershell:Get-Service"):
            name = str(entry.get("Name", ""))
            if name:
                services.append(
                    {
                        "name": name,
                        "display_name": str(entry.get("DisplayName", "")),
                        "status": _status_name(entry.get("Status", "")),
                    }
                )
        services = services[:limit]
        return {"count": len(services), "services": services}, None
    except DiagnosticCommandError as exc:
        return {"count": 0, "services": []}, str(exc)


def _live_service_details(name: str, timeout_s: float) -> tuple[dict, str | None]:
    clean = validate_service_name(name)
    parts: dict[str, Any] = {}
    failures: list[str] = []
    try:
        payload = _run_powershell(
            _STATUS_SCRIPT_TEMPLATE.replace("{name}", clean),
            "powershell:Get-Service",
            timeout_s,
        )
        rows = _as_dict_list(payload, "powershell:Get-Service")
        if rows:
            row = rows[0]
            parts["status"] = {
                "name": str(row.get("Name", clean)),
                "display_name": str(row.get("DisplayName", "")),
                "status": _status_name(row.get("Status", "")),
            }
    except DiagnosticCommandError as exc:
        failures.append(f"status: {exc}")
    try:
        payload = _run_powershell(
            _STARTUP_SCRIPT_TEMPLATE.replace("{name}", clean),
            "powershell:Get-CimInstance Win32_Service",
            timeout_s,
        )
        rows = _as_dict_list(payload, "powershell:Get-CimInstance Win32_Service")
        if rows:
            row = rows[0]
            parts["startup"] = {
                "name": str(row.get("Name", clean)),
                "startup_type": str(row.get("StartMode", "")),
                "state": str(row.get("State", "")),
            }
    except DiagnosticCommandError as exc:
        failures.append(f"startup: {exc}")
    try:
        payload = _run_powershell(
            _DEPENDENCIES_TEMPLATE.replace("{name}", clean),
            "powershell:Get-Service/Dependencies",
            timeout_s,
        )
        rows = _as_dict_list(payload, "powershell:Get-Service/Dependencies")
        row = rows[0] if rows else {}
        parts["dependencies"] = {
            "required_services": [str(i) for i in row.get("required", []) or []][:32],
            "dependent_services": [str(i) for i in row.get("dependent", []) or []][:32],
        }
    except DiagnosticCommandError as exc:
        failures.append(f"dependencies: {exc}")
    if not parts:
        return {"name": clean}, "; ".join(failures) or "no details available"
    data = {"name": clean, **parts}
    return data, ("; ".join(failures) if failures else None)


def _live_os(timeout_s: float) -> tuple[dict, str | None]:
    try:
        payload = _run_powershell(
            _OS_SCRIPT, "powershell:Get-CimInstance Win32_OperatingSystem", timeout_s
        )
        rows = _as_dict_list(payload, "powershell:Get-CimInstance Win32_OperatingSystem")
        if not rows:
            raise DiagnosticCommandError(
                "No Win32_OperatingSystem record returned.",
                "powershell:Get-CimInstance Win32_OperatingSystem",
            )
        row = rows[0]
        return {
            "caption": str(row.get("Caption", "")),
            "version": str(row.get("Version", "")),
            "build_number": str(row.get("BuildNumber", "")),
            "os_architecture": str(row.get("OSArchitecture", "")),
            "last_boot_up_time": str(row.get("LastBootUpTime", "")),
            "windows_directory": str(row.get("WindowsDirectory", "")),
        }, None
    except DiagnosticCommandError as exc:
        fallback = {
            "caption": platform.system(),
            "version": platform.version(),
            "build_number": "",
            "os_architecture": platform.machine(),
            "last_boot_up_time": "",
            "windows_directory": "",
            "fallback": "stdlib platform module (live OS query failed)",
        }
        return fallback, str(exc)


def _live_events(timeout_s: float, cap: int) -> tuple[dict, str | None]:
    source = "powershell:Get-WinEvent System"
    try:
        payload = _run_powershell(_EVENTS_SCRIPT, source, timeout_s)
        rows = _as_dict_list(payload, source)
        events = []
        for row in rows:
            events.append(
                {
                    "time_created": str(row.get("TimeCreated", "")),
                    "id": row.get("Id"),
                    "level": str(row.get("LevelDisplayName", "")),
                    "provider": str(row.get("ProviderName", "")),
                    "message": str(row.get("Message", ""))[:MAX_EVENT_MESSAGE_CHARS],
                }
            )
        return {
            "log": "System",
            "window_hours": 24,
            "levels": [1, 2, 3],
            "scan_cap": 200,
            "scanned": len(rows),
            "events": events[:cap],
            "note": (
                f"Most recent {min(len(events), cap)} of {len(rows)} examined "
                "System entries (Levels 1-3, last 24h). Absence of matches "
                "does not prove absence of failure."
            ),
        }, None
    except DiagnosticCommandError as exc:
        return {
            "log": "System", "window_hours": 24, "scanned": 0, "events": [],
        }, str(exc)


def _live_network(timeout_s: float, limit: int) -> dict[str, tuple[dict, str | None]]:
    out: dict[str, tuple[dict, str | None]] = {}
    try:
        payload = _run_powershell(
            _ADAPTERS_SCRIPT, "powershell:Get-NetAdapter", timeout_s
        )
        adapters = []
        for row in _as_dict_list(payload, "powershell:Get-NetAdapter"):
            name = str(row.get("Name", ""))
            if name:
                adapters.append(
                    {
                        "name": name,
                        "description": str(row.get("InterfaceDescription", "")),
                        "status": str(row.get("Status", "")),
                        "link_speed": str(row.get("LinkSpeed", "")),
                        "mac_address": str(row.get("MacAddress", "")),
                        "interface_index": row.get("InterfaceIndex"),
                    }
                )
        adapters = adapters[:16]
        out["adapters"] = ({"count": len(adapters), "adapters": adapters}, None)
    except DiagnosticCommandError as exc:
        out["adapters"] = ({"count": 0, "adapters": []}, str(exc))
    try:
        payload = _run_powershell(_IP_SCRIPT, "powershell:Get-NetIPAddress", timeout_s)
        addresses = []
        for row in _as_dict_list(payload, "powershell:Get-NetIPAddress"):
            ip = str(row.get("IPAddress", ""))
            if ip:
                addresses.append(
                    {
                        "interface": str(row.get("InterfaceAlias", "")),
                        "ip_address": ip,
                        "prefix_length": row.get("PrefixLength"),
                        "address_family": str(row.get("AddressFamily", "")),
                        "prefix_origin": str(row.get("PrefixOrigin", "")),
                    }
                )
        addresses = addresses[:limit]
        out["ip"] = ({"count": len(addresses), "addresses": addresses}, None)
    except DiagnosticCommandError as exc:
        out["ip"] = ({"count": 0, "addresses": []}, str(exc))
    try:
        payload = _run_powershell(
            _DNS_SCRIPT, "powershell:Get-DnsClientServerAddress", timeout_s
        )
        configs = []
        for row in _as_dict_list(payload, "powershell:Get-DnsClientServerAddress"):
            servers = row.get("ServerAddresses", [])
            if not isinstance(servers, list):
                servers = [servers]
            iface = str(row.get("InterfaceAlias", ""))
            if iface:
                configs.append(
                    {
                        "interface": iface,
                        "servers": [str(s) for s in servers if str(s)],
                    }
                )
        out["dns"] = ({"count": len(configs), "interfaces": configs}, None)
    except DiagnosticCommandError as exc:
        out["dns"] = ({"count": 0, "interfaces": []}, str(exc))
    try:
        payload = _run_powershell(
            _CONNECTIONS_SCRIPT, "powershell:Get-NetTCPConnection Established", timeout_s
        )
        connections = []
        for row in _as_dict_list(payload, "powershell:Get-NetTCPConnection Established"):
            connections.append(
                {
                    "local_address": str(row.get("LocalAddress", "")),
                    "local_port": row.get("LocalPort"),
                    "remote_address": str(row.get("RemoteAddress", "")),
                    "remote_port": row.get("RemotePort"),
                    "state": str(row.get("State", "")),
                    "owning_process_id": row.get("OwningProcess"),
                }
            )
        connections = connections[:25]
        out["connections"] = (
            {"count": len(connections), "connections": connections}, None
        )
    except DiagnosticCommandError as exc:
        out["connections"] = ({"count": 0, "connections": []}, str(exc))
    return out


def _summarize_task_action(raw: dict) -> dict[str, str]:
    return {
        "execute": str(raw.get("Execute", raw.get("execute", ""))),
        "arguments": _truncate(
            str(raw.get("Arguments", raw.get("arguments", ""))), MAX_ARGUMENT_CHARS
        ),
        "working_directory": str(
            raw.get("WorkingDirectory", raw.get("working_directory", ""))
        ),
    }


def _live_tasks(timeout_s: float, limit: int) -> tuple[dict, str | None]:
    try:
        payload = _run_powershell(
            _TASKS_SCRIPT, "powershell:Get-ScheduledTask", timeout_s
        )
        definitions = _as_dict_list(payload, "powershell:Get-ScheduledTask")
    except DiagnosticCommandError as exc:
        return {"count": 0, "total_scanned": 0, "tasks": []}, str(exc)
    try:
        info_payload = _run_powershell(
            _TASK_INFO_SCRIPT, "powershell:Get-ScheduledTaskInfo", timeout_s
        )
        infos = _as_dict_list(info_payload, "powershell:Get-ScheduledTaskInfo")
    except DiagnosticCommandError:
        infos = []
    by_key = {
        (str(i.get("TaskPath", "")), str(i.get("TaskName", ""))): i for i in infos
    }
    tasks: list[dict[str, Any]] = []
    for row in definitions:
        name = str(row.get("TaskName", ""))
        path = str(row.get("TaskPath", ""))
        if not name:
            continue
        if path.lower().startswith("\\microsoft"):
            continue
        info = by_key.get((path, name), {})
        last_result = info.get("LastTaskResult")
        principal = row.get("Principal") or {}
        tasks.append(
            {
                "task_name": name,
                "task_path": path,
                "state": str(row.get("State", "")),
                "author": str(row.get("Author", "")),
                "description": str(row.get("Description", ""))[:MAX_DESCRIPTION_CHARS],
                "principal": {
                    "user_id": str(principal.get("UserId", "")),
                    "logon_type": str(principal.get("LogonType", "")),
                    "run_level": str(principal.get("RunLevel", "")),
                },
                "triggers": [
                    {
                        "type": str(t.get("Type", "")),
                        "enabled": t.get("Enabled"),
                        "start_boundary": str(t.get("StartBoundary", "")),
                    }
                    for t in _as_list(row.get("Triggers"))
                ][:8],
                "actions": [
                    _summarize_task_action(a) for a in _as_list(row.get("Actions"))
                ][:8],
                "last_run_time": str(info.get("LastRunTime", "")),
                "last_task_result": last_result,
                "last_run_succeeded": (
                    (last_result == 0) if isinstance(last_result, int) else None
                ),
                "next_run_time": str(info.get("NextRunTime", "")),
            }
        )
    total = len(definitions)
    kept = tasks[:limit]
    return {"count": len(kept), "total_scanned": total, "tasks": kept}, None


def _live_procs(timeout_s: float, limit: int) -> tuple[dict, str | None]:
    safe_limit = max(1, min(int(limit), 100))
    script = _PROC_LIST_TEMPLATE.replace("{limit}", str(safe_limit))
    source = "powershell:Get-CimInstance Win32_Process"
    try:
        payload = _run_powershell(script, source, timeout_s)
        rows = _as_dict_list(payload, source)
    except DiagnosticCommandError as exc:
        return {"found": False, "processes": [], "snapshot": True}, str(exc)
    processes = []
    for row in rows:
        try:
            memory_mb = round(int(row.get("WorkingSetSize", 0)) / (1024 * 1024), 1)
        except (TypeError, ValueError):
            memory_mb = None
        processes.append(
            {
                "pid": row.get("ProcessId"),
                "name": str(row.get("Name", "")),
                "executable_path": str(row.get("ExecutablePath", "") or ""),
                "started": str(row.get("CreationDate", "")),
                "memory_mb": memory_mb,
            }
        )
    return {
        "found": bool(processes),
        "snapshot": True,
        "processes": processes,
        "note": "Top processes by memory; executable path only, never command lines.",
    }, None


# ---------------------------------------------------------------------------
# Deterministic fixtures (offline tests + sample packages)
# ---------------------------------------------------------------------------

FIXTURE_HOSTNAME = "FIELD-PC-042"
FIXTURE_USERNAME = "FieldTech"

_FIXTURE_SERVICES = [
    {"name": "wuauserv", "display_name": "Windows Update", "status": "Stopped"},
    {"name": "BITS", "display_name": "Background Intelligent Transfer Service", "status": "Stopped"},
    {"name": "Spooler", "display_name": "Print Spooler", "status": "Running"},
    {"name": "Dhcp", "display_name": "DHCP Client", "status": "Running"},
    {"name": "Dnscache", "display_name": "DNS Client", "status": "Running"},
    {"name": "Winmgmt", "display_name": "Windows Management Instrumentation", "status": "Running"},
    {"name": "w32time", "display_name": "Windows Time", "status": "Stopped"},
    {"name": "LanmanWorkstation", "display_name": "Workstation", "status": "Running"},
]


def _fixture_payloads() -> dict[str, Any]:
    return {
        "services": {
            "count": len(_FIXTURE_SERVICES),
            "services": [dict(s) for s in _FIXTURE_SERVICES],
        },
        "service_details": {
            "name": "wuauserv",
            "status": {
                "name": "wuauserv", "display_name": "Windows Update",
                "status": "Stopped",
            },
            "startup": {
                "name": "wuauserv", "startup_type": "Manual",
                "state": "Stopped",
            },
        },
        "os": {
            "caption": "Microsoft Windows 11 Pro (fixture)",
            "version": "10.0.22631",
            "build_number": "22631",
            "os_architecture": "64-bit",
            "last_boot_up_time": "2026-10-26T07:58:11",
            "windows_directory": "C:\\Windows",
        },
        "events": {
            "log": "System",
            "window_hours": 24,
            "levels": [1, 2, 3],
            "scan_cap": 200,
            "scanned": 187,
            "events": [
                {
                    "time_created": "2026-10-25T21:13:47",
                    "id": 7023,
                    "level": "Error",
                    "provider": "Service Control Manager",
                    "message": (
                        "The Windows Update service terminated on FIELD-PC-042 "
                        "with the following error: the system cannot find the "
                        "path specified."
                    ),
                },
                {
                    "time_created": "2026-10-25T21:14:03",
                    "id": 7036,
                    "level": "Information",
                    "provider": "Service Control Manager",
                    "message": "The Windows Update service entered the stopped state.",
                },
                {
                    "time_created": "2026-10-26T08:02:44",
                    "id": 1014,
                    "level": "Warning",
                    "provider": "DNS Client Events",
                    "message": (
                        "Name resolution for example.local timed out; reported by "
                        "CORP\\FieldTech from fieldtech@example.com."
                    ),
                },
            ],
            "note": "Fixture sample: 187 examined, 3 shown.",
        },
        "adapters": {
            "count": 2,
            "adapters": [
                {
                    "name": "Wi-Fi",
                    "description": "Intel Wireless Adapter (fixture)",
                    "status": "Up",
                    "link_speed": "866 Mbps",
                    "mac_address": "AA-BB-CC-DD-EE-01",
                    "interface_index": 12,
                },
                {
                    "name": "Ethernet",
                    "description": "Realtek Ethernet Adapter (fixture)",
                    "status": "Disconnected",
                    "link_speed": "",
                    "mac_address": "AA-BB-CC-DD-EE-02",
                    "interface_index": 7,
                },
            ],
        },
        "ip": {
            "count": 3,
            "addresses": [
                {"interface": "Wi-Fi", "ip_address": "192.168.1.20", "prefix_length": 24, "address_family": "IPv4", "prefix_origin": "Dhcp"},
                {"interface": "Wi-Fi", "ip_address": "fe80::1", "prefix_length": 64, "address_family": "IPv6", "prefix_origin": "WellKnown"},
                {"interface": "Loopback", "ip_address": "127.0.0.1", "prefix_length": 8, "address_family": "IPv4", "prefix_origin": "WellKnown"},
            ],
        },
        "dns": {
            "count": 2,
            "interfaces": [
                {"interface": "Wi-Fi", "servers": ["192.168.1.1", "1.1.1.1"]},
                {"interface": "Ethernet", "servers": []},
            ],
        },
        "connections": {
            "count": 2,
            "connections": [
                {"local_address": "127.0.0.1", "local_port": 8000, "remote_address": "127.0.0.1", "remote_port": 52134, "state": "Established", "owning_process_id": 1234},
                {"local_address": "192.168.1.20", "local_port": 52311, "remote_address": "93.184.216.34", "remote_port": 443, "state": "Established", "owning_process_id": 5678},
            ],
        },
        "tasks": {
            "count": 2,
            "total_scanned": 2,
            "tasks": [
                {
                    "task_name": "RookweldSync",
                    "task_path": "\\Rookweld\\",
                    "state": "Ready",
                    "author": "ROOKWELD\\FieldTech",
                    "description": "Fixture: periodic ROOKWELD synchronization.",
                    "principal": {"user_id": "FieldTech", "logon_type": "Interactive", "run_level": "Limited"},
                    "triggers": [{"type": "MSFT_TaskTimeTrigger", "enabled": True, "start_boundary": "2026-10-26T08:00:00"}],
                    "actions": [{"execute": "powershell.exe", "arguments": "-NoProfile -File C:\\Rookweld\\sync.ps1 -Token abc123secret", "working_directory": "C:\\Rookweld"}],
                    "last_run_time": "2026-10-26T08:00:04",
                    "last_task_result": 0,
                    "last_run_succeeded": True,
                    "next_run_time": "2026-10-26T08:10:00",
                },
                {
                    "task_name": "ContosoBackup",
                    "task_path": "\\Contoso\\",
                    "state": "Ready",
                    "author": "Contoso",
                    "description": "Fixture: nightly backup (contact ops@example.com, password: hunter2).",
                    "principal": {"user_id": "SYSTEM", "logon_type": "ServiceAccount", "run_level": "Highest"},
                    "triggers": [{"type": "MSFT_TaskDailyTrigger", "enabled": True, "start_boundary": "2026-10-26T02:00:00"}],
                    "actions": [{"execute": "C:\\Contoso\\backup.exe", "arguments": "--target \\\\nas\\share", "working_directory": ""}],
                    "last_run_time": "2026-10-26T02:00:11",
                    "last_task_result": 0,
                    "last_run_succeeded": True,
                    "next_run_time": "2026-10-27T02:00:00",
                },
            ],
        },
        "procs": {
            "found": True,
            "snapshot": True,
            "processes": [
                {"pid": 1234, "name": "FieldRook.exe", "executable_path": "C:\\FieldRook\\FieldRook.exe", "started": "2026-10-26T07:58:40", "memory_mb": 182.4},
                {"pid": 5678, "name": "svchost.exe", "executable_path": "C:\\Windows\\System32\\svchost.exe", "started": "2026-10-26T07:58:12", "memory_mb": 96.1},
                {"pid": 42, "name": "explorer.exe", "executable_path": "C:\\Windows\\explorer.exe", "started": "2026-10-26T07:58:20", "memory_mb": 88.7},
            ],
            "note": "Fixture snapshot; executable path only, never command lines.",
        },
    }


@dataclass
class CollectionResult:
    entries: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    os_info: dict[str, str] = field(default_factory=dict)
    hostname_hash: str = ""
    target_hint: str | None = None
    duration_ms: int = 0
    consent_receipt: list[dict[str, str]] = field(default_factory=list)
    fixture_mode: bool = False


def manifest_os_info(os_payload: dict[str, Any] | None) -> dict[str, str]:
    """Derive the manifest ``os`` block from a collection (stdlib fallback)."""
    if isinstance(os_payload, dict) and os_payload.get("caption"):
        return {
            "platform": str(os_payload.get("caption", "")),
            "version": str(os_payload.get("version", "")),
            "build": str(os_payload.get("build_number", "")),
        }
    return {
        "platform": f"{platform.system()} {platform.release()}",
        "version": platform.version(),
        "build": "",
    }


def collect_all(
    categories: list[str] | None = None,
    consent_ack: bool = False,
    timeout_s: float = 30.0,
    fixture: bool = False,
    hostname: str | None = None,
    target_hint: str | None = None,
    username: str | None = None,
    service_name: str = "",
    service_limit: int = 50,
    task_limit: int = 40,
    process_limit: int = 25,
    event_cap: int = 25,
) -> CollectionResult:
    """Run the read-only collectors and return redacted manifest entries.

    Entries are NOT chunked here; callers pre-chunk via ``chunker.py``
    before :func:`manifest.build_manifest`. Raises :class:`PermissionError`
    unless ``consent_ack`` is true, :class:`ValueError` for unknown
    categories or a hint that leaks the hostname.
    """
    keys = list(categories) if categories else sorted(CATEGORIES)
    unknown = [k for k in keys if k not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown collection categories: {unknown}.")
    if not consent_ack:
        raise PermissionError(
            "Collection consent not acknowledged: show format_consent_screen() "
            "and pass consent_ack=True."
        )
    started = time.monotonic()
    host = hostname if hostname is not None else socket.gethostname()
    identity = build_identity(host, target_hint)
    hint = identity["target_hint"]
    warnings: list[str] = []
    consent_receipt = [
        {
            "category": key,
            "label": CATEGORIES[key]["label"],
            "privilege": CATEGORIES[key]["privilege"],
            "consent": CATEGORIES[key]["consent"],
        }
        for key in keys
    ]
    suffix = "fixture" if fixture else "live"
    if fixture:
        warnings.append("fixture mode: deterministic synthetic data (offline tests).")
    live_ok = fixture or powershell_available()
    if not fixture and not powershell_available():
        warnings.append(
            "PowerShell unavailable on this host; emitting honest no-data error entries."
        )
    fixtures = _fixture_payloads() if fixture or not live_ok else {}

    raw_items: list[dict[str, Any]] = []

    def _take(key: str, live: tuple[dict, str | None] | None, fix: str) -> tuple[dict, str | None]:
        if fixture or not live_ok:
            return dict(fixtures[fix]), None
        assert live is not None
        return live

    if "services" in keys:
        payload, err = _take(
            "services",
            _live_services(timeout_s, service_limit) if live_ok and not fixture else None,
            "services",
        )
        raw_items.append(
            {
                "category": "service_list", "data": payload, "error": err,
                "tool_name": "list_services",
                "tool_args": {"limit": max(1, min(int(service_limit), 200))},
            }
        )
        if service_name.strip():
            clean = validate_service_name(service_name)
            if fixture or not live_ok:
                detail, detail_err = dict(fixtures["service_details"]), None
                detail["name"] = clean
            else:
                detail, detail_err = _live_service_details(clean, timeout_s)
            raw_items.append(
                {
                    "category": "service_details", "data": detail,
                    "error": detail_err, "tool_name": "get_service_details",
                    "tool_args": {"name": clean},
                }
            )
    os_payload: dict[str, Any] | None = None
    if "os" in keys:
        payload, err = _take(
            "os", _live_os(timeout_s) if live_ok and not fixture else None, "os"
        )
        os_payload = payload
        raw_items.append(
            {
                "category": "os_info", "data": payload, "error": err,
                "tool_name": "get_os_info", "tool_args": {},
            }
        )
    if "events" in keys:
        payload, err = _take(
            "events",
            _live_events(timeout_s, event_cap) if live_ok and not fixture else None,
            "events",
        )
        raw_items.append(
            {"category": "event_log", "data": payload, "error": err}
        )
    if "network" in keys:
        if fixture or not live_ok:
            net = {
                "adapters": (dict(fixtures["adapters"]), None),
                "ip": (dict(fixtures["ip"]), None),
                "dns": (dict(fixtures["dns"]), None),
                "connections": (dict(fixtures["connections"]), None),
            }
        else:
            net = _live_network(timeout_s, 40)
        specs = [
            ("net_adapters", "adapters", "get_network_adapters", {"limit": 16}),
            ("ip_config", "ip", "get_ip_config", {"limit": 40}),
            ("dns_config", "dns", "get_dns_config", {}),
            ("connections", "connections", "get_connections", {"limit": 25}),
        ]
        for category, slot, tool, args in specs:
            payload, err = net[slot]
            raw_items.append(
                {
                    "category": category, "data": payload, "error": err,
                    "tool_name": tool, "tool_args": dict(args),
                }
            )
    if "tasks" in keys:
        payload, err = _take(
            "tasks",
            _live_tasks(timeout_s, task_limit) if live_ok and not fixture else None,
            "tasks",
        )
        raw_items.append(
            {
                "category": "scheduled_tasks", "data": payload, "error": err,
                "tool_name": "get_scheduled_tasks",
                "tool_args": {
                    "folder": "\\",
                    "name_contains": "",
                    "action_contains": "",
                    "include_microsoft": False,
                    "limit": max(1, min(int(task_limit), 100)),
                },
            }
        )
    if "procs" in keys:
        payload, err = _take(
            "procs",
            _live_procs(timeout_s, process_limit) if live_ok and not fixture else None,
            "procs",
        )
        raw_items.append(
            {"category": "process_info", "data": payload, "error": err}
        )

    entries: list[dict[str, Any]] = []
    for position, item in enumerate(raw_items, start=1):
        redacted, count = redact_data(item["data"], host, hint, username)
        assert isinstance(redacted, dict)
        redacted.setdefault("provenance", {})["redaction_count"] = count
        # M024.1: emit RAW entries (no sha256/size). Live data can exceed
        # 12KB (e.g. Fury's task list); build_entry would raise here,
        # before __main__ gets to pre-chunk (D3a). Hashing happens in
        # manifest.finalize_entries after chunking.
        raw_entry: dict[str, Any] = {
            "id": f"c-{position}",
            "category": item["category"],
            "source_suffix": suffix,
            "collected_at": utc_now_iso(),
            "data": redacted,
        }
        if item.get("tool_name") is not None:
            raw_entry["tool_name"] = item["tool_name"]
        if item.get("tool_args") is not None:
            raw_entry["tool_args"] = item["tool_args"]
        if item.get("error") is not None:
            raw_entry["error"] = item["error"]
        entries.append(raw_entry)
    duration_ms = int((time.monotonic() - started) * 1000)
    return CollectionResult(
        entries=entries,
        warnings=warnings,
        os_info=manifest_os_info(os_payload or fixtures.get("os")),
        hostname_hash=str(identity["hostname_hash"]),
        target_hint=hint,
        duration_ms=duration_ms,
        consent_receipt=consent_receipt,
        fixture_mode=fixture,
    )
