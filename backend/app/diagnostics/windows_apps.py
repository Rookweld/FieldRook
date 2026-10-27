"""Bounded application crash/hang diagnostics (read-only).

Reads Application Error (1000), WER (1001), Application Hang (1002), and
.NET Runtime (1026) events from the Windows Application log. Never reads
crash dumps, application files, or user documents.
"""

from __future__ import annotations

import re

from .event_search import MAX_EVENT_MESSAGE_CHARS, SCAN_CAP
from .windows_tools import (
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

SOURCE_CRASHES = "powershell:Get-WinEvent Application/Crashes"
CRASH_EVENT_IDS = (1000, 1001, 1002, 1026)

_CRASH_SCRIPT_TEMPLATE = (
    "Get-WinEvent -FilterHashtable @{LogName='Application'; "
    "ID=1000,1001,1002,1026; StartTime=(Get-Date).AddHours(-{hours})} "
    "-MaxEvents {cap} -ErrorAction SilentlyContinue "
    "| Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message "
    "| ConvertTo-Json -Compress -Depth 3"
)

_APP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._\-()]{0,63}$")
_FAULTING_APP = re.compile(r"Faulting application name:\s*([^\s,]+)", re.IGNORECASE)
_FAULTING_MODULE = re.compile(r"Faulting module name:\s*([^\s,]+)", re.IGNORECASE)
_EXCEPTION_CODE = re.compile(r"Exception code:\s*(0x[0-9a-fA-F]+)", re.IGNORECASE)
_FAULT_OFFSET = re.compile(r"Fault offset:\s*(0x[0-9a-fA-F]+)", re.IGNORECASE)
_FAULT_PID = re.compile(r"Faulting process id:\s*(0x[0-9a-fA-F]+|\d+)", re.IGNORECASE)
_HANG_APP = re.compile(r"program\s+([^\s]+\.exe)", re.IGNORECASE)


def validate_app_name(value: str) -> str:
    """Validate an application-name filter (empty string = no filter)."""
    text = (value or "").strip()
    if not text:
        return ""
    if not _APP_NAME_PATTERN.match(text):
        raise ValueError(
            f"Invalid application name {value!r}: use 1-64 characters of "
            "letters, digits, space, and . _ - ( )."
        )
    return text


def _parse_crash(entry: dict) -> dict:
    message = str(entry.get("Message", ""))
    event_id = entry.get("Id")
    app = ""
    match = _FAULTING_APP.search(message) or _HANG_APP.search(message)
    if match:
        app = match.group(1)
    module = _FAULTING_MODULE.search(message)
    code = _EXCEPTION_CODE.search(message)
    offset = _FAULT_OFFSET.search(message)
    pid = _FAULT_PID.search(message)
    kind = {1000: "application_error", 1001: "error_report", 1002: "application_hang"}.get(
        event_id if isinstance(event_id, int) else -1, "runtime_fault"
    )
    return {
        "time_created": str(entry.get("TimeCreated", "")),
        "id": event_id,
        "kind": kind,
        "level": str(entry.get("LevelDisplayName", "")),
        "provider": str(entry.get("ProviderName", "")),
        "app_name": app,
        "faulting_module": module.group(1) if module else "",
        "exception_code": code.group(1) if code else "",
        "fault_offset": offset.group(1) if offset else "",
        "fault_pid": pid.group(1) if pid else "",
        "message": message[:MAX_EVENT_MESSAGE_CHARS],
    }


def search_crashes_live(
    app_name: str, hours: int, max_events: int, timeout_s: float
) -> dict:
    """Search the live Application log for crash/hang evidence (bounded)."""
    needle = validate_app_name(app_name).lower()
    script = _CRASH_SCRIPT_TEMPLATE.replace("{hours}", str(hours)).replace(
        "{cap}", str(SCAN_CAP)
    )
    try:
        payload = _run_powershell(script, SOURCE_CRASHES, timeout_s)
        entries = _as_dict_list(payload, SOURCE_CRASHES)
    except (DiagnosticCommandError, ValueError) as exc:
        return {
            "log": "Application",
            "event_ids": list(CRASH_EVENT_IDS),
            "hours": hours,
            "completed": False,
            "scanned": 0,
            "matched": 0,
            "crashes": [],
            "error": str(exc),
        }
    parsed = [_parse_crash(entry) for entry in entries]
    if needle:
        parsed = [item for item in parsed if needle in item["app_name"].lower()]
    matched = parsed[:max_events]
    return {
        "log": "Application",
        "event_ids": list(CRASH_EVENT_IDS),
        "hours": hours,
        "completed": True,
        "scanned": len(entries),
        "matched": len(matched),
        "truncated_matches": len(parsed) > len(matched),
        "crashes": matched,
    }
