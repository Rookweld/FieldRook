"""Bounded process and service-relationship diagnostics (read-only).

Collects executable metadata, PID-to-service mapping, uptime, and service
dependencies. Full process command lines are NEVER collected: only the
executable path is read, so secrets in arguments cannot leak.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .windows_tools import (
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

SOURCE_PROCESS = "powershell:Get-CimInstance Win32_Process"
SOURCE_PROC_SERVICES = "powershell:Get-CimInstance Win32_Service/ProcessId"
SOURCE_DEPENDENCIES = "powershell:Get-Service/Dependencies"

_PROCESS_BY_NAME_TEMPLATE = (
    "Get-CimInstance -ClassName Win32_Process -Filter \"Name='{name}'\" "
    "| Select-Object ProcessId,Name,ExecutablePath,CreationDate,WorkingSetSize "
    "| ConvertTo-Json -Compress -Depth 3"
)
_PROCESS_BY_PID_TEMPLATE = (
    "Get-CimInstance -ClassName Win32_Process -Filter \"ProcessId={pid}\" "
    "| Select-Object ProcessId,Name,ExecutablePath,CreationDate,WorkingSetSize "
    "| ConvertTo-Json -Compress -Depth 3"
)
_PROC_SERVICES_TEMPLATE = (
    "Get-CimInstance -ClassName Win32_Service -Filter \"ProcessId={pid}\" "
    "| Select-Object Name,DisplayName,State "
    "| ConvertTo-Json -Compress -Depth 3"
)
_SERVICE_PID_TEMPLATE = (
    "Get-CimInstance -ClassName Win32_Service -Filter \"Name='{name}'\" "
    "| Select-Object Name,State,ProcessId "
    "| ConvertTo-Json -Compress -Depth 3"
)
_DEPENDENCIES_TEMPLATE = (
    "$s = Get-Service -Name '{name}' -ErrorAction Stop; "
    "@{required = @($s.ServicesDependedOn | Select-Object -ExpandProperty Name); "
    "dependent = @($s.DependentServices | Select-Object -ExpandProperty Name)} "
    "| ConvertTo-Json -Compress -Depth 3"
)

_PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._\-()]{0,63}$")
_CIM_DATE_PATTERN = re.compile(r"(\d{14})")
_JSON_DATE_PATTERN = re.compile(r"/Date\((\d+)([+-]\d{4})?\)/")


def validate_process_name(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if not _PROCESS_NAME_PATTERN.match(text):
        raise ValueError(
            f"Invalid process name {value!r}: use 1-64 characters of "
            "letters, digits, space, and . _ - ( )."
        )
    return text


def validate_pid(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Invalid process id {value!r}: expected an integer.")
    if value < 0 or value > 2_147_483_647:
        raise ValueError(f"Invalid process id {value!r}.")
    return value


def _uptime_seconds(creation: str) -> int | None:
    text = creation or ""
    started: datetime | None = None
    json_match = _JSON_DATE_PATTERN.search(text)
    if json_match:
        # ConvertTo-Json serializes CIM datetimes as /Date(ms-since-epoch)/.
        try:
            started = datetime.fromtimestamp(int(json_match.group(1)) / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            started = None
    else:
        match = _CIM_DATE_PATTERN.search(text)
        if match:
            try:
                started = datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                started = None
    if started is None:
        return None
    delta = (datetime.now(timezone.utc) - started).total_seconds()
    return int(delta) if delta >= 0 else None


def _summarize_process(entry: dict) -> dict:
    working_set = entry.get("WorkingSetSize")
    try:
        memory_mb = round(int(working_set) / (1024 * 1024), 1)
    except (TypeError, ValueError):
        memory_mb = None
    creation = str(entry.get("CreationDate", ""))
    return {
        "pid": entry.get("ProcessId"),
        "name": str(entry.get("Name", "")),
        "executable_path": str(entry.get("ExecutablePath", "") or ""),
        "started": creation,
        "uptime_s": _uptime_seconds(creation),
        "memory_mb": memory_mb,
    }


def resolve_service_pid_live(name: str, timeout_s: float) -> dict:
    """Resolve a service name to its hosting PID (read-only).

    Returns {"name", "state", "pid"} with pid None when the service is
    stopped or has no process. Raises ValueError for invalid names so the
    registry converts it into an error output, never a shell failure.
    """
    from .service_allowlist import validate_service_name

    clean = validate_service_name(name)
    script = _SERVICE_PID_TEMPLATE.replace("{name}", clean)
    rows = _as_dict_list(
        _run_powershell(script, SOURCE_PROC_SERVICES, timeout_s), SOURCE_PROC_SERVICES
    )
    if not rows:
        raise ValueError(f"Service {clean!r} was not found.")
    row = rows[0]
    raw_pid = row.get("ProcessId", 0)
    pid = int(raw_pid) if isinstance(raw_pid, int) and raw_pid > 0 else None
    return {"name": clean, "state": str(row.get("State", "") or "Unknown"), "pid": pid}


def get_process_live(name: str, pid: int, timeout_s: float, service_name: str = "") -> dict:
    """Read one process (by name, pid, or hosting service) plus hosted services."""
    from .service_allowlist import validate_service_name

    clean_name = validate_process_name(name)
    clean_pid = validate_pid(pid)
    clean_service = validate_service_name(service_name) if (service_name or "").strip() else ""
    selectors = bool(clean_name) + bool(clean_pid) + bool(clean_service)
    if selectors != 1:
        raise ValueError("Provide exactly one of process name, pid, or service name.")
    service_ctx: dict | None = None
    if clean_service:
        service_ctx = resolve_service_pid_live(clean_service, timeout_s)
        if not service_ctx["pid"]:
            return {
                "found": False,
                "processes": [],
                "services": [],
                "service": service_ctx,
            }
        clean_pid = int(service_ctx["pid"])
    if clean_pid:
        script = _PROCESS_BY_PID_TEMPLATE.replace("{pid}", str(clean_pid))
    else:
        script = _PROCESS_BY_NAME_TEMPLATE.replace("{name}", clean_name)
    entries = _as_dict_list(_run_powershell(script, SOURCE_PROCESS, timeout_s), SOURCE_PROCESS)
    if not entries:
        result: dict = {"found": False, "processes": [], "services": []}
        if service_ctx:
            result["service"] = service_ctx
        return result
    processes = [_summarize_process(entry) for entry in entries[:8]]
    services: list[dict] = []
    seen: set[str] = set()
    for process in processes:
        proc_pid = process.get("pid")
        if not isinstance(proc_pid, int):
            continue
        script = _PROC_SERVICES_TEMPLATE.replace("{pid}", str(proc_pid))
        try:
            rows = _as_dict_list(
                _run_powershell(script, SOURCE_PROC_SERVICES, timeout_s), SOURCE_PROC_SERVICES
            )
        except DiagnosticCommandError:
            continue
        for row in rows:
            svc_name = str(row.get("Name", ""))
            if svc_name and svc_name not in seen:
                seen.add(svc_name)
                services.append(
                    {
                        "name": svc_name,
                        "display_name": str(row.get("DisplayName", "")),
                        "state": str(row.get("State", "")),
                    }
                )
    result = {
        "found": True,
        "match_count": len(entries),
        "truncated_matches": len(entries) > len(processes),
        "processes": processes,
        "services": services,
    }
    if service_ctx:
        result["service"] = service_ctx
    return result


def get_service_dependencies_live(name: str, timeout_s: float) -> dict:
    """Read service dependency names (required + dependent), names only."""
    from .service_allowlist import validate_service_name

    clean = validate_service_name(name)
    script = _DEPENDENCIES_TEMPLATE.replace("{name}", clean)
    payload = _run_powershell(script, SOURCE_DEPENDENCIES, timeout_s)
    rows = _as_dict_list(payload, SOURCE_DEPENDENCIES)
    data = rows[0] if rows else {}
    required = [str(item) for item in data.get("required", []) or []][:32]
    dependent = [str(item) for item in data.get("dependent", []) or []][:32]
    return {"name": clean, "required_services": required, "dependent_services": dependent}
