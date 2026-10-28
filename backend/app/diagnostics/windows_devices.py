"""Read-only Windows device and volume diagnostics (BETA, new).

Read-only operations (proposed for the allowlist; LEAD adds them):

  D1. Get-PnpDevice (device status + problem codes, bounded list)
  D2. Get-CimInstance Win32_LogicalDisk (local volumes: size + free space)

Nothing here changes system state. New allowlisted commands are proposed
by BETA via PROPOSED_ALLOWLIST_ADDITIONS and added by LEAD
(security-sensitive per FORGE_CONTRACTS.md section 3).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .windows_tools import (
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

PROPOSED_ALLOWLIST_ADDITIONS: tuple[str, ...] = (
    "Get-PnpDevice",
    "Get-CimInstance Win32_LogicalDisk",
)

SOURCE_DEVICES = "powershell:Get-PnpDevice"
SOURCE_VOLUMES = "powershell:Get-CimInstance Win32_LogicalDisk"

_DEVICES_SCRIPT = (
    "Get-PnpDevice -ErrorAction SilentlyContinue "
    "| Select-Object FriendlyName,InstanceId,Class,Status,Problem "
    "| ConvertTo-Json -Compress -Depth 3"
)
_VOLUMES_SCRIPT = (
    'Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DriveType=3" '
    "| Select-Object DeviceID,VolumeName,FileSystem,Size,FreeSpace "
    "| ConvertTo-Json -Compress -Depth 3"
)

DEVICE_STATUSES = ("OK", "Error", "Degraded", "Unknown")


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListDevicesArgs(StrictArgs):
    """Args model for the proposed list_devices tool (lead reviews)."""

    limit: int = Field(default=50, ge=1, le=100)
    status: str = Field(default="", max_length=16)


class ListVolumesArgs(StrictArgs):
    """Args model for the proposed list_volumes tool (lead reviews)."""


def validate_device_status(value: str) -> str:
    """Validate a PnP status filter (empty string = no filter)."""
    text = (value or "").strip()
    if not text:
        return ""
    for allowed in DEVICE_STATUSES:
        if allowed.lower() == text.lower():
            return allowed
    raise ValueError(f"Invalid device status {value!r}: expected one of {', '.join(DEVICE_STATUSES)} or ''.")


def validate_limit(value: int, minimum: int = 1, maximum: int = 100) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid limit {value!r}: expected an integer.")
    if not minimum <= value <= maximum:
        raise ValueError(f"Invalid limit {value!r}: expected {minimum}-{maximum}.")
    return value


def _summarize_device(entry: dict) -> dict[str, Any]:
    raw_problem = entry.get("Problem", 0)
    try:
        problem = int(raw_problem)
    except (TypeError, ValueError):
        problem = -1
    return {
        "name": str(entry.get("FriendlyName", "")),
        "instance_id": str(entry.get("InstanceId", "")),
        "device_class": str(entry.get("Class", "")),
        "status": str(entry.get("Status", "")),
        "problem_code": problem,
        "has_problem": problem != 0,
    }


def list_devices_live(timeout_s: float, limit: int = 50, status: str = "") -> list[dict[str, Any]]:
    """List PnP devices with status/problem codes (read-only, bounded)."""
    clean_limit = validate_limit(limit)
    clean_status = validate_device_status(status)
    payload = _run_powershell(_DEVICES_SCRIPT, SOURCE_DEVICES, timeout_s)
    devices = [_summarize_device(entry) for entry in _as_dict_list(payload, SOURCE_DEVICES)]
    devices = [device for device in devices if device["name"] or device["instance_id"]]
    if clean_status:
        devices = [device for device in devices if device["status"] == clean_status]
    return devices[:clean_limit]


def _summarize_volume(entry: dict) -> dict[str, Any]:
    def _as_int(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        text = str(value or "").strip()
        return int(text) if text.isdigit() else None

    size = _as_int(entry.get("Size"))
    free = _as_int(entry.get("FreeSpace"))
    used_pct: float | None = None
    if size and free is not None and size > 0 and 0 <= free <= size:
        used_pct = round((size - free) / size * 100, 1)
    return {
        "drive": str(entry.get("DeviceID", "")),
        "label": str(entry.get("VolumeName", "") or ""),
        "filesystem": str(entry.get("FileSystem", "") or ""),
        "size_bytes": size,
        "free_bytes": free,
        "used_pct": used_pct,
    }


def list_volumes_live(timeout_s: float) -> list[dict[str, Any]]:
    """List local disk volumes with size and free space (read-only)."""
    payload = _run_powershell(_VOLUMES_SCRIPT, SOURCE_VOLUMES, timeout_s)
    volumes = [_summarize_volume(entry) for entry in _as_dict_list(payload, SOURCE_VOLUMES)]
    return [volume for volume in volumes if volume["drive"]]


_FIXTURE_DEVICES: list[dict[str, Any]] = [
    {
        "name": "Intel Wireless Adapter (fixture)",
        "instance_id": "PCI\\VEN_8086&DEV_2725\\FIXTURE001",
        "device_class": "Net",
        "status": "OK",
        "problem_code": 0,
        "has_problem": False,
    },
    {
        "name": "USB Audio Device (fixture)",
        "instance_id": "USB\\VID_046D&PID_0AAD\\FIXTURE002",
        "device_class": "AudioEndpoint",
        "status": "Error",
        "problem_code": 28,
        "has_problem": True,
    },
    {
        "name": "Print Spooler Virtual Printer (fixture)",
        "instance_id": "SW\\FIXTURE003",
        "device_class": "Printer",
        "status": "Degraded",
        "problem_code": 0,
        "has_problem": False,
    },
]

_FIXTURE_VOLUMES: list[dict[str, Any]] = [
    {
        "drive": "C:",
        "label": "Windows",
        "filesystem": "NTFS",
        "size_bytes": 512_000_000_000,
        "free_bytes": 128_000_000_000,
        "used_pct": 75.0,
    },
    {
        "drive": "D:",
        "label": "Data",
        "filesystem": "NTFS",
        "size_bytes": 1_000_000_000_000,
        "free_bytes": 800_000_000_000,
        "used_pct": 20.0,
    },
]


def list_devices_fixture(limit: int = 50, status: str = "") -> list[dict[str, Any]]:
    """Deterministic mirror of list_devices_live over fixture data."""
    clean_limit = validate_limit(limit)
    clean_status = validate_device_status(status)
    devices = [dict(device) for device in _FIXTURE_DEVICES]
    if clean_status:
        devices = [device for device in devices if device["status"] == clean_status]
    return devices[:clean_limit]


def get_fixture_devices() -> list[dict[str, Any]]:
    return [dict(device) for device in _FIXTURE_DEVICES]


def list_volumes_fixture() -> list[dict[str, Any]]:
    """Deterministic mirror of list_volumes_live over fixture data."""
    return [dict(volume) for volume in _FIXTURE_VOLUMES]


def get_fixture_volumes() -> list[dict[str, Any]]:
    return [dict(volume) for volume in _FIXTURE_VOLUMES]


__all__ = [
    "DEVICE_STATUSES",
    "PROPOSED_ALLOWLIST_ADDITIONS",
    "SOURCE_DEVICES",
    "SOURCE_VOLUMES",
    "ListDevicesArgs",
    "ListVolumesArgs",
    "get_fixture_devices",
    "get_fixture_volumes",
    "list_devices_fixture",
    "list_devices_live",
    "list_volumes_fixture",
    "list_volumes_live",
    "validate_device_status",
    "validate_limit",
]
