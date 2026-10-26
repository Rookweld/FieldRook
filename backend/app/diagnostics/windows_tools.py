"""Allowlisted, read-only Windows diagnostics.

Exactly three read-only operations exist:

  1. Get-Service (list + status)
  2. Get-CimInstance Win32_Service (startup type)
  3. Get-WinEvent on the System log (bounded sample)

No other command can run through this module, and service names are validated
before interpolation. Nothing here changes system state.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

ALLOWLISTED_COMMANDS: tuple[str, ...] = (
    "Get-Service",
    "Get-CimInstance Win32_Service",
    "Get-WinEvent -LogName System",
)

SOURCE_LIST = "powershell:Get-Service"
SOURCE_STATUS = "powershell:Get-Service"
SOURCE_STARTUP = "powershell:Get-CimInstance Win32_Service"
SOURCE_EVENTS = "powershell:Get-WinEvent System"

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
_EVENTS_SCRIPT = (
    "Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2,3; "
    "StartTime=(Get-Date).AddHours(-24)} -MaxEvents 100 -ErrorAction SilentlyContinue "
    "| Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message "
    "| ConvertTo-Json -Compress -Depth 3"
)

MAX_EVENT_MESSAGE_CHARS = 500
MAX_MATCHED_EVENTS = 25


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


def list_services(timeout_s: float) -> list[dict]:
    payload = _run_powershell(_LIST_SCRIPT, SOURCE_LIST, timeout_s)
    services = []
    for entry in _as_dict_list(payload, SOURCE_LIST):
        services.append(
            {
                "name": str(entry.get("Name", "")),
                "display_name": str(entry.get("DisplayName", "")),
                "status": str(entry.get("Status", "")),
            }
        )
    return [service for service in services if service["name"]]


def get_service_status(name: str, timeout_s: float) -> dict:
    script = _STATUS_SCRIPT_TEMPLATE.replace("{name}", name)
    payload = _run_powershell(script, SOURCE_STATUS, timeout_s)
    entries = _as_dict_list(payload, SOURCE_STATUS)
    if not entries:
        raise DiagnosticCommandError(f"Service '{name}' was not found.", SOURCE_STATUS)
    entry = entries[0]
    return {
        "name": str(entry.get("Name", name)),
        "display_name": str(entry.get("DisplayName", "")),
        "status": str(entry.get("Status", "")),
        "service_type": str(entry.get("ServiceType", "")),
    }


def get_startup_type(name: str, timeout_s: float) -> dict:
    script = _STARTUP_SCRIPT_TEMPLATE.replace("{name}", name)
    payload = _run_powershell(script, SOURCE_STARTUP, timeout_s)
    entries = _as_dict_list(payload, SOURCE_STARTUP)
    if not entries:
        raise DiagnosticCommandError(f"No Win32_Service record for '{name}'.", SOURCE_STARTUP)
    entry = entries[0]
    return {
        "name": str(entry.get("Name", name)),
        "startup_type": str(entry.get("StartMode", "")),
        "state": str(entry.get("State", "")),
        "start_name": str(entry.get("StartName", "")),
    }


def get_event_logs(name: str, display_name: str, timeout_s: float) -> dict:
    payload = _run_powershell(_EVENTS_SCRIPT, SOURCE_EVENTS, timeout_s)
    needle = name.lower()
    matched: list[dict] = []
    scanned = 0
    for entry in _as_dict_list(payload, SOURCE_EVENTS):
        scanned += 1
        haystack = f"{entry.get('ProviderName', '')} {entry.get('Message', '')}".lower()
        if needle and needle in haystack:
            matched.append(
                {
                    "time_created": str(entry.get("TimeCreated", "")),
                    "id": entry.get("Id"),
                    "level": str(entry.get("LevelDisplayName", "")),
                    "provider": str(entry.get("ProviderName", "")),
                    "message": str(entry.get("Message", ""))[:MAX_EVENT_MESSAGE_CHARS],
                }
            )
        if len(matched) >= MAX_MATCHED_EVENTS:
            break
    return {
        "log": "System",
        "window_hours": 24,
        "scanned": scanned,
        "matched": len(matched),
        "filter": f"entries mentioning '{name}'",
        "display_name_hint": display_name,
        "events": matched,
    }
