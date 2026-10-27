"""Allowlisted, read-only Windows service diagnostics.

Read-only operations in this module:

  1. Get-Service (list + status)
  2. Get-CimInstance Win32_Service (startup type)

Event-log searches live in event_search.py; OS/network tools in windows_net.py.
No other command can run through this layer, and service names are validated
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
    "Get-WinEvent -LogName Application",
    "Get-CimInstance Win32_OperatingSystem",
    "Get-NetAdapter",
    "Get-NetIPAddress",
    "Get-DnsClientServerAddress",
    "Get-NetTCPConnection Established",
    "Get-ScheduledTask",
    "Get-ScheduledTaskInfo",
    "Get-WinEvent -LogName Application/Crashes",
    "Get-CimInstance Win32_Process",
    "Get-CimInstance Win32_Service/ProcessId",
    "Get-Service/Dependencies",
    "Resolve-DnsName",
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

# Windows PowerShell serializes ServiceControllerStatus as its numeric value.
_SERVICE_STATUS_NAMES = {
    1: "Stopped",
    2: "StartPending",
    3: "StopPending",
    4: "Running",
    5: "ContinuePending",
    6: "PausePending",
    7: "Paused",
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


# ServiceType is a flags enum; Windows PowerShell serializes it numerically.
_SERVICE_TYPE_NAMES = (
    (256, "InteractiveProcess"),
    (32, "Win32ShareProcess"),
    (16, "Win32OwnProcess"),
    (8, "RecognizerDriver"),
    (4, "Adapter"),
    (2, "SystemDriver"),
    (1, "KernelDriver"),
)


def _service_type_name(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    number: int | None = None
    if isinstance(value, int):
        number = value
    else:
        text = str(value or "").strip()
        if not text:
            return "Unknown"
        if text.isdigit():
            number = int(text)
        else:
            return text
    parts = [name for bit, name in _SERVICE_TYPE_NAMES if number & bit]
    remainder = number
    for bit, _ in _SERVICE_TYPE_NAMES:
        remainder &= ~bit
    if remainder:
        parts.append(str(remainder))
    return " | ".join(parts) if parts else "Unknown"


def _service_type_value(value: object) -> int | None:
    """Preserve the original numeric ServiceType alongside the mapped name."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


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
                "status": _status_name(entry.get("Status", "")),
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
    raw_type = entry.get("ServiceType", "")
    return {
        "name": str(entry.get("Name", name)),
        "display_name": str(entry.get("DisplayName", "")),
        "status": _status_name(entry.get("Status", "")),
        "service_type": _service_type_name(raw_type),
        "service_type_value": _service_type_value(raw_type),
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
