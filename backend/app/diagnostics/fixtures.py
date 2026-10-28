"""Deterministic fixture data and simulated analysis.

Fixtures stand in where real Windows diagnostics cannot run (tests, demos,
non-Windows hosts). Fixture payloads are fixed constants; only the collection
timestamps vary. Simulated analysis is derived strictly from the evidence
it receives and always labels itself `simulated`.
"""

from __future__ import annotations

from typing import Any

from ..config import SIMULATED_MODEL_NAME
from ..schemas import AnalysisResult, DiagnosticBundle, EvidenceItem, ObservedFact, RootCause

FIXTURE_SERVICES: list[dict[str, str]] = [
    {"name": "wuauserv", "display_name": "Windows Update", "status": "Stopped"},
    {"name": "BITS", "display_name": "Background Intelligent Transfer Service", "status": "Stopped"},
    {"name": "Spooler", "display_name": "Print Spooler", "status": "Running"},
    {"name": "Dhcp", "display_name": "DHCP Client", "status": "Running"},
    {"name": "Dnscache", "display_name": "DNS Client", "status": "Running"},
    {"name": "Winmgmt", "display_name": "Windows Management Instrumentation", "status": "Running"},
    {"name": "w32time", "display_name": "Windows Time", "status": "Stopped"},
    {"name": "LanmanWorkstation", "display_name": "Workstation", "status": "Running"},
]

_FIXTURE_STARTUP: dict[str, dict[str, str]] = {
    "wuauserv": {"startup_type": "Manual", "state": "Stopped", "start_name": "LocalSystem"},
    "bits": {"startup_type": "Manual", "state": "Stopped", "start_name": "LocalSystem"},
    "spooler": {"startup_type": "Auto", "state": "Running", "start_name": "LocalSystem"},
    "dhcp": {"startup_type": "Auto", "state": "Running", "start_name": "LocalSystem"},
    "dnscache": {"startup_type": "Auto", "state": "Running", "start_name": "NetworkService"},
    "winmgmt": {"startup_type": "Auto", "state": "Running", "start_name": "LocalSystem"},
    "w32time": {"startup_type": "Manual", "state": "Stopped", "start_name": "LocalService"},
    "lanmanworkstation": {"startup_type": "Auto", "state": "Running", "start_name": "LocalSystem"},
}

_FIXTURE_EVENTS: dict[str, list[dict[str, object]]] = {
    "wuauserv": [
        {
            "time_created": "2026-10-25T21:13:47",
            "id": 7023,
            "level": "Error",
            "provider": "Service Control Manager",
            "message": "The Windows Update service terminated with the following error: "
            "The system cannot find the path specified.",
        },
        {
            "time_created": "2026-10-25T21:14:03",
            "id": 7036,
            "level": "Information",
            "provider": "Service Control Manager",
            "message": "The Windows Update service entered the stopped state.",
        },
    ],
    "bits": [
        {
            "time_created": "2026-10-25T18:02:11",
            "id": 7036,
            "level": "Information",
            "provider": "Service Control Manager",
            "message": "The Background Intelligent Transfer Service service entered the stopped state.",
        },
    ],
    "spooler": [
        {
            "time_created": "2026-10-26T07:59:52",
            "id": 7036,
            "level": "Information",
            "provider": "Service Control Manager",
            "message": "The Print Spooler service entered the running state.",
        },
    ],
    "w32time": [
        {
            "time_created": "2026-10-24T12:00:00",
            "id": 7036,
            "level": "Information",
            "provider": "Service Control Manager",
            "message": "The Windows Time service entered the stopped state.",
        },
    ],
}

_FIXTURE_OS_INFO: dict[str, str] = {
    "caption": "Microsoft Windows 11 Pro (fixture)",
    "version": "10.0.22631",
    "build_number": "22631",
    "os_architecture": "64-bit",
    "last_boot_up_time": "2026-10-26T07:58:11",
    "windows_directory": "C:\\Windows",
}

_FIXTURE_ADAPTERS: list[dict[str, Any]] = [
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
]

_FIXTURE_IP_ADDRESSES: list[dict[str, Any]] = [
    {"interface": "Wi-Fi", "ip_address": "192.168.1.20", "prefix_length": 24, "address_family": "IPv4", "prefix_origin": "Dhcp"},
    {"interface": "Wi-Fi", "ip_address": "fe80::1", "prefix_length": 64, "address_family": "IPv6", "prefix_origin": "WellKnown"},
    {"interface": "Loopback", "ip_address": "127.0.0.1", "prefix_length": 8, "address_family": "IPv4", "prefix_origin": "WellKnown"},
]

_FIXTURE_DNS: list[dict[str, Any]] = [
    {"interface": "Wi-Fi", "servers": ["192.168.1.1", "1.1.1.1"]},
    {"interface": "Ethernet", "servers": []},
]

_FIXTURE_CONNECTIONS: list[dict[str, Any]] = [
    {"local_address": "127.0.0.1", "local_port": 8000, "remote_address": "127.0.0.1", "remote_port": 52134, "state": "Established", "owning_process_id": 1234},
    {"local_address": "192.168.1.20", "local_port": 52311, "remote_address": "93.184.216.34", "remote_port": 443, "state": "Established", "owning_process_id": 5678},
]

# Generic entries so keyword searches have a deterministic pool beyond
# service-specific fixtures. None of these mention wuauserv/BITS, keeping the
# M001 per-service samples exact.
_GENERIC_EVENTS: list[tuple[str, dict[str, object]]] = [
    ("System", {"time_created": "2026-10-26T07:59:52", "id": 7036, "level": "Information", "provider": "Service Control Manager", "message": "The Print Spooler service entered the running state."}),
    ("System", {"time_created": "2026-10-26T08:01:20", "id": 7036, "level": "Information", "provider": "Service Control Manager", "message": "The DNS Client service entered the running state."}),
    ("System", {"time_created": "2026-10-26T08:02:44", "id": 1014, "level": "Warning", "provider": "DNS Client Events", "message": "Name resolution for the name example.local timed out after none of the configured DNS servers responded."}),
    ("Application", {"time_created": "2026-10-26T09:15:00", "id": 1000, "level": "Error", "provider": "Application Error", "message": "Faulting application name: ContosoVPN.exe, faulting module: UNKNOWN. Exception code 0xc0000005."}),
    ("Application", {"time_created": "2026-10-26T09:15:31", "id": 1002, "level": "Warning", "provider": "Application Hang", "message": "The program ContosoVPN.exe stopped responding and was closed."}),
]


def _key(name: str) -> str:
    return name.strip().lower()


def _service_state_overrides() -> dict[str, str]:
    """Test-only state flips: FIELDROOK_FIXTURE_SERVICE_STATES="a=Running,b=Stopped".

    Lets scenario tests change a fixture service's state mid-investigation
    without touching real Windows services. Unknown names are ignored.
    """
    import os

    overrides: dict[str, str] = {}
    for pair in os.environ.get("FIELDROOK_FIXTURE_SERVICE_STATES", "").split(","):
        if "=" not in pair:
            continue
        name, _, state = pair.partition("=")
        name = name.strip().lower()
        state = state.strip()
        if name and state:
            overrides[name] = state
    return overrides


def _missing_fixture_services() -> set[str]:
    """Test-only removals: FIELDROOK_FIXTURE_MISSING_SERVICES="a,b"."""
    import os

    return {
        name.strip().lower()
        for name in os.environ.get("FIELDROOK_FIXTURE_MISSING_SERVICES", "").split(",")
        if name.strip()
    }


def get_fixture_status(name: str) -> dict[str, str] | None:
    if _key(name) in _missing_fixture_services():
        return None
    for service in FIXTURE_SERVICES:
        if _key(service["name"]) == _key(name):
            record = dict(service)
            override = _service_state_overrides().get(_key(name))
            if override:
                record["status"] = override
            return record
    return None


def get_fixture_startup(name: str) -> dict[str, str] | None:
    record = _FIXTURE_STARTUP.get(_key(name))
    return dict(record) if record is not None else None


def get_fixture_events(name: str) -> list[dict[str, object]] | None:
    if get_fixture_status(name) is None:
        return None
    return [dict(event) for event in _FIXTURE_EVENTS.get(_key(name), [])]


def get_fixture_os_info() -> dict[str, Any]:
    return dict(_FIXTURE_OS_INFO)


def get_fixture_adapters() -> list[dict[str, Any]]:
    return [dict(adapter) for adapter in _FIXTURE_ADAPTERS]


def get_fixture_ip_addresses() -> list[dict[str, Any]]:
    return [dict(address) for address in _FIXTURE_IP_ADDRESSES]


def get_fixture_dns() -> list[dict[str, Any]]:
    return [dict(entry) for entry in _FIXTURE_DNS]


def get_fixture_connections() -> list[dict[str, Any]]:
    return [dict(connection) for connection in _FIXTURE_CONNECTIONS]


_FIXTURE_TASKS: list[dict[str, Any]] = [
    {
        "task_name": "RookweldSync",
        "task_path": "\\Rookweld\\",
        "state": "Ready",
        "author": "ROOKWELD",
        "description": "Fixture: periodic ROOKWELD synchronization.",
        "principal": {"user_id": "TestUser", "logon_type": "Interactive", "run_level": "Limited"},
        "triggers": [
            {
                "type": "MSFT_TaskTimeTrigger",
                "enabled": True,
                "start_boundary": "2026-10-26T08:00:00",
                "repetition_interval": "PT10M",
            }
        ],
        "actions": [
            {
                "execute": "powershell.exe",
                "arguments": "-NoProfile -File C:\\Rookweld\\sync.ps1 -Token abc123secret",
                "working_directory": "C:\\Rookweld",
            }
        ],
        "last_run_time": "2026-10-26T19:40:00",
        "last_task_result": 0,
        "last_run_succeeded": True,
        "next_run_time": "2026-10-26T19:50:00",
        "missed_runs": 0,
    },
    {
        "task_name": "FieldRookDemoPhantom",
        "task_path": "\\FieldRookDemo\\",
        "state": "Ready",
        "author": "FieldRook demo fixture",
        "description": "Fixture: synthetic recurring PowerShell task with a misplaced window-hiding argument (Scenario A). Not a real system task.",
        "principal": {"user_id": "TestUser", "logon_type": "Interactive", "run_level": "Limited"},
        "triggers": [
            {
                "type": "MSFT_TaskTimeTrigger",
                "enabled": True,
                "start_boundary": "2026-10-26T08:00:00",
                "repetition_interval": "PT5M",
            }
        ],
        "actions": [
            {
                "execute": "powershell.exe",
                "arguments": "-NoProfile -File C:\\FieldRookDemo\\phantom.ps1",
                "working_directory": "C:\\FieldRookDemo -WindowStyle Hidden",
            }
        ],
        "last_run_time": "2026-10-26T19:45:00",
        "last_task_result": 2147942667,
        "last_run_succeeded": False,
        "next_run_time": "2026-10-26T19:50:00",
        "missed_runs": 0,
    },
    {
        "task_name": "GoogleUpdateTaskMachineUA",
        "task_path": "\\",
        "state": "Ready",
        "author": "Google",
        "description": "Fixture: updater task.",
        "principal": {"user_id": "SYSTEM", "logon_type": "Service", "run_level": "Highest"},
        "triggers": [{"type": "MSFT_TaskDailyTrigger", "enabled": True, "start_boundary": "2026-10-26T09:00:00", "days_interval": 1}],
        "actions": [
            {
                "execute": "C:\\Program Files\\Google\\Update\\GoogleUpdate.exe",
                "arguments": "/ua /installsource scheduler",
                "working_directory": "",
            }
        ],
        "last_run_time": "2026-10-26T09:00:12",
        "last_task_result": 0,
        "last_run_succeeded": True,
        "next_run_time": "2026-10-27T09:00:00",
        "missed_runs": 0,
    },
    {
        "task_name": "EdgeUpdateBackground",
        "task_path": "\\Microsoft\\Edge\\",
        "state": "Ready",
        "author": "Microsoft",
        "description": "Fixture: Microsoft-subtree task for exclusion tests.",
        "principal": {"user_id": "SYSTEM", "logon_type": "Service", "run_level": "Highest"},
        "triggers": [{"type": "MSFT_TaskLogonTrigger", "enabled": True}],
        "actions": [{"execute": "C:\\Edge\\Updater.exe", "arguments": "/background", "working_directory": ""}],
        "last_run_time": "2026-10-26T07:58:30",
        "last_task_result": 0,
        "last_run_succeeded": True,
        "next_run_time": "",
        "missed_runs": 0,
    },
    {
        "task_name": "BackupDocs",
        "task_path": "\\",
        "state": "Disabled",
        "author": "TestUser",
        "description": "Fixture: disabled task with a failing last result.",
        "principal": {"user_id": "TestUser", "logon_type": "Interactive", "run_level": "Limited"},
        "triggers": [{"type": "MSFT_TaskDailyTrigger", "enabled": False, "start_boundary": "2026-10-26T02:00:00", "days_interval": 1}],
        "actions": [{"execute": "C:\\Tools\\backup.exe", "arguments": "--full", "working_directory": ""}],
        "last_run_time": "2026-10-25T02:00:05",
        "last_task_result": 1,
        "last_run_succeeded": False,
        "next_run_time": "",
        "missed_runs": 2,
    },
]

# Fixture data models a machine whose interactive user is TestUser, so the
# privacy sanitizer masks that name deterministically in fixture outputs.
FIXTURE_USERNAME = "TestUser"


def get_fixture_scheduled_tasks() -> list[dict[str, Any]]:
    import copy

    return copy.deepcopy(_FIXTURE_TASKS)


_FIXTURE_DEMO_WORKER: dict[str, Any] = {
    "worker_id": "demo-worker",
    "status": "healthy",
    "pid": 4242,
    "detail": "ok",
    "updated_at": 1793050800.0,
    "heartbeat_age_s": 1.2,
    "process_verified": True,
}


_FIXTURE_CRASHES: list[dict[str, Any]] = [
    {
        "time_created": "2026-10-26T14:32:11",
        "id": 1000,
        "kind": "application_error",
        "level": "Error",
        "provider": "Application Error",
        "app_name": "EXCEL.EXE",
        "faulting_module": "KERNELBASE.dll",
        "exception_code": "0xc0000005",
        "fault_offset": "0x0000000000034f69",
        "fault_pid": "0x2a41",
        "message": "Faulting application name: EXCEL.EXE, version: 16.0.0.1. Faulting module name: KERNELBASE.dll. Exception code: 0xc0000005.",
    },
    {
        "time_created": "2026-10-26T11:05:44",
        "id": 1000,
        "kind": "application_error",
        "level": "Error",
        "provider": "Application Error",
        "app_name": "ContosoApp.exe",
        "faulting_module": "ContosoApp.exe",
        "exception_code": "0xe0434352",
        "fault_offset": "0x0000000000000000",
        "fault_pid": "0x1b22",
        "message": "Faulting application name: ContosoApp.exe. Faulting module name: ContosoApp.exe. Exception code: 0xe0434352 (.NET runtime).",
    },
    {
        "time_created": "2026-10-25T16:12:09",
        "id": 1002,
        "kind": "application_hang",
        "level": "Error",
        "provider": "Application Hang",
        "app_name": "mscopilot_proxy.exe",
        "faulting_module": "",
        "exception_code": "",
        "fault_offset": "",
        "fault_pid": "",
        "message": "The program mscopilot_proxy.exe stopped interacting with Windows and was closed.",
    },
    {
        "time_created": "2026-10-25T09:41:52",
        "id": 1026,
        "kind": "runtime_fault",
        "level": "Error",
        "provider": ".NET Runtime",
        "app_name": "ContosoApp.exe",
        "faulting_module": "",
        "exception_code": "0xe0434352",
        "fault_offset": "",
        "fault_pid": "",
        "message": "Application: ContosoApp.exe. Framework Version: v4.0. Unhandled exception, process terminated.",
    },
    {
        "time_created": "2026-10-26T15:00:00",
        "id": 1001,
        "kind": "error_report",
        "level": "Information",
        "provider": "Windows Error Reporting",
        "app_name": "",
        "faulting_module": "",
        "exception_code": "",
        "fault_offset": "",
        "fault_pid": "",
        "message": "Fault bucket 1234567890, type 5. Event Name: APPCRASH. (No faulting application parsed.)",
    },
]


def search_fixture_crashes(app_name: str, hours: int, max_events: int) -> dict[str, Any]:
    """Deterministic mirror of the live crash search over fixture data."""
    import os

    needle = (app_name or "").strip().lower()
    pool = [dict(item) for item in _FIXTURE_CRASHES]
    # Test-only injection: FIELDROOK_FIXTURE_CRASH_EXTRA="OUTLOOK.EXE" prepends
    # a newer synthetic crash so scenario tests can change the evidence
    # mid-investigation.
    extra = os.environ.get("FIELDROOK_FIXTURE_CRASH_EXTRA", "").strip()
    if extra:
        app = extra if extra.lower().endswith(".exe") else f"{extra}.EXE"
        pool.insert(
            0,
            {
                "time_created": "2026-10-27T07:30:00",
                "id": 1000,
                "kind": "application_error",
                "level": "Error",
                "provider": "Application Error",
                "app_name": app,
                "faulting_module": "ntdll.dll",
                "exception_code": "0xc0000374",
                "fault_offset": "0x00000000000e0000",
                "fault_pid": "0x1b22",
                "message": f"Faulting application name: {app}. Faulting module name: ntdll.dll. Exception code: 0xc0000374.",
            },
        )
    matched = [item for item in pool if not needle or needle in item["app_name"].lower()]
    bounded = matched[:max_events]
    return {
        "log": "Application",
        "event_ids": [1000, 1001, 1002, 1026],
        "hours": hours,
        "completed": True,
        "scanned": len(pool),
        "matched": len(bounded),
        "truncated_matches": len(matched) > len(bounded),
        "crashes": bounded,
    }


_FIXTURE_PROCESSES: list[dict[str, Any]] = [
    {
        "pid": 1234,
        "name": "EXCEL.EXE",
        "executable_path": "C:\\Program Files\\Contoso\\EXCEL.EXE",
        "started": "20261026113000.000000+060",
        "uptime_s": 7200,
        "memory_mb": 412.5,
        "services": [],
    },
    {
        "pid": 5678,
        "name": "svchost.exe",
        "executable_path": "C:\\Windows\\System32\\svchost.exe",
        "started": "20261026081500.000000+060",
        "uptime_s": 86400,
        "memory_mb": 96.0,
        "services": [
            {"name": "wuauserv", "display_name": "Windows Update", "state": "Running"},
        ],
    },
]


def get_fixture_process(name: str, pid: int, service_name: str = "") -> dict[str, Any]:
    """Deterministic process lookup. Exactly one of name/pid/service selects."""
    clean_name = (name or "").strip().lower()
    clean_service = (service_name or "").strip().lower()
    selectors = bool(clean_name) + bool(pid) + bool(clean_service)
    if selectors != 1:
        raise ValueError("Provide exactly one of process name, pid, or service name.")
    service_ctx: dict[str, Any] | None = None
    if clean_service:
        states = {s["name"].strip().lower(): s["status"] for s in FIXTURE_SERVICES}
        states.update(_service_state_overrides())
        matches = [
            dict(p)
            for p in _FIXTURE_PROCESSES
            if any(s.get("name", "").lower() == clean_service for s in p["services"])
        ]
        service_ctx = {
            "name": (service_name or "").strip(),
            "state": states.get(clean_service, "Unknown"),
            "pid": matches[0]["pid"] if matches else None,
        }
        if not matches:
            return {"found": False, "processes": [], "services": [], "service": service_ctx}
    elif pid:
        matches = [dict(p) for p in _FIXTURE_PROCESSES if p["pid"] == pid]
    else:
        matches = [dict(p) for p in _FIXTURE_PROCESSES if p["name"].lower() == clean_name]
    if not matches:
        return {"found": False, "processes": [], "services": []}
    services: list[dict[str, Any]] = []
    for match in matches[:8]:
        services.extend(match.pop("services"))
    result: dict[str, Any] = {
        "found": True,
        "match_count": len(matches),
        "truncated_matches": len(matches) > 8,
        "processes": matches[:8],
        "services": services,
    }
    if service_ctx:
        result["service"] = service_ctx
    return result


_FIXTURE_DEPENDENCIES: dict[str, dict[str, list[str]]] = {
    "wuauserv": {
        "required_services": ["rpcss"],
        "dependent_services": ["BITS"],
    },
    "bits": {
        "required_services": ["rpcss", "EventSystem"],
        "dependent_services": [],
    },
}


def get_fixture_dependencies(name: str) -> dict[str, Any]:
    key = (name or "").strip().lower()
    entry = _FIXTURE_DEPENDENCIES.get(key, {"required_services": [], "dependent_services": []})
    return {
        "name": (name or "").strip(),
        "required_services": list(entry["required_services"]),
        "dependent_services": list(entry["dependent_services"]),
    }


_FIXTURE_RESOLUTIONS: dict[str, list[str]] = {
    "example.com": ["93.184.216.34"],
    "localhost": ["127.0.0.1"],
}


def resolve_fixture_hostname(hostname: str) -> dict[str, Any]:
    """Deterministic mirror of the single-query DNS test."""
    clean = (hostname or "").strip().rstrip(".")
    addresses = _FIXTURE_RESOLUTIONS.get(clean.lower(), [])
    return {
        "hostname": clean,
        "succeeded": bool(addresses),
        "query_ms": 1,
        "addresses": list(addresses),
        "error": None if addresses else f"No fixture records for {clean!r}.",
    }


def get_fixture_demo_worker() -> dict[str, Any]:
    """Fixture worker health; FIELDROOK_FIXTURE_WORKER=failing simulates a fault."""
    import os

    record = dict(_FIXTURE_DEMO_WORKER)
    if os.environ.get("FIELDROOK_FIXTURE_WORKER", "").strip().lower() == "failing":
        record["status"] = "failed"
        record["detail"] = "Simulated fault (mode=failing)."
    return record


def _fixture_event_pool() -> list[tuple[str, dict[str, object], str]]:
    pool: list[tuple[str, dict[str, object], str]] = [
        (log, dict(event), "") for log, event in _GENERIC_EVENTS
    ]
    displays = {
        service["name"].strip().lower(): service["display_name"]
        for service in FIXTURE_SERVICES
    }
    for key, events in _FIXTURE_EVENTS.items():
        tags = f"{key} {displays.get(key, '')}"
        for event in events:
            pool.append(("System", dict(event), tags))
    return pool


def search_fixture_events(
    keywords: list[str], logs: list[str], hours: int, max_events: int
) -> dict[str, Any]:
    """Deterministic mirror of the live event search over fixture data."""
    lowered = [keyword.lower() for keyword in keywords if keyword]
    per_log: list[dict[str, Any]] = []
    for log in logs:
        pool = [
            (event, tags)
            for entry_log, event, tags in _fixture_event_pool()
            if entry_log == log
        ]
        matched = [
            event
            for event, tags in pool
            if any(
                kw in f"{event.get('provider', '')} {event.get('message', '')} {tags}".lower()
                for kw in lowered
            )
        ]
        per_log.append(
            {
                "log": log,
                "completed": True,
                "scanned": len(pool),
                "matched": len(matched),
                "events": matched[:max_events],
                "note": (
                    f"Fixture pool: examined {len(pool)} entries (last {hours}h window "
                    f"claimed); showing {min(len(matched), max_events)} of {len(matched)} matches."
                ),
            }
        )
    return {
        "window_hours": hours,
        "levels": [1, 2, 3],
        "scan_cap": len(_fixture_event_pool()),
        "keywords": keywords,
        "logs": per_log,
    }


def build_simulated_analysis(bundle: DiagnosticBundle) -> AnalysisResult:
    """Build a deterministic, clearly simulated assessment from a bundle.

    Every fact restates bundle data with real evidence ids. Causes are generic
    hypotheses, never verified conclusions. No action is taken or claimed.
    """
    by_category = {item.category: item for item in bundle.items}
    status_item = by_category.get("service_status")
    startup_item = by_category.get("startup_type")
    events_item = by_category.get("event_log")
    ok_ids = {item.category: item.id for item in bundle.items if item.error is None}

    status_value = ""
    display = bundle.display_name or bundle.service_name
    if status_item is not None and status_item.error is None:
        status_value = str(status_item.data.get("status", ""))
        display = str(status_item.data.get("display_name", display)) or display

    facts: list[ObservedFact] = []
    if status_item is not None and status_item.error is None and "service_status" in ok_ids:
        facts.append(
            ObservedFact(
                statement=(
                    f"Service '{bundle.service_name}' ('{display}') "
                    f"reports status '{status_value}'."
                ),
                evidence_ids=[ok_ids["service_status"]],
            )
        )
    if startup_item is not None and startup_item.error is None and "startup_type" in ok_ids:
        facts.append(
            ObservedFact(
                statement=(
                    f"Configured startup type is "
                    f"'{startup_item.data.get('startup_type', '')}' "
                    f"(account '{startup_item.data.get('start_name', '')}')."
                ),
                evidence_ids=[ok_ids["startup_type"]],
            )
        )
    if events_item is not None and events_item.error is None and "event_log" in ok_ids:
        facts.append(
            ObservedFact(
                statement=(
                    f"Bounded System-log sample returned "
                    f"{events_item.data.get('matched', 0)} related entries "
                    f"(scanned {events_item.data.get('scanned', 0)})."
                ),
                evidence_ids=[ok_ids["event_log"]],
            )
        )
    if not facts:
        facts.append(
            ObservedFact(
                statement=f"No usable evidence items were collected for "
                f"'{bundle.service_name}'.",
                evidence_ids=[],
            )
        )

    state = status_value.lower()
    if state == "stopped":
        causes = [
            RootCause(
                title="Service is stopped while set to manual start",
                description=(
                    "A stopped service with manual startup is often expected "
                    "behavior rather than a failure. Whether this state is a "
                    "problem depends on site expectations, which are unverified."
                ),
                likelihood="medium",
                evidence_ids=[
                    ok_ids[c] for c in ("service_status", "startup_type") if c in ok_ids
                ],
            ),
            RootCause(
                title="Service stopped because of an error outside the bounded sample",
                description=(
                    "The bounded event sample may have missed the failure record. "
                    "This remains a hypothesis until the full log around the "
                    "failure time is reviewed."
                ),
                likelihood="low",
                evidence_ids=[ok_ids[c] for c in ("event_log",) if c in ok_ids],
            ),
        ]
    elif state == "running":
        causes = [
            RootCause(
                title="Service reports healthy; the reported symptom may originate elsewhere",
                description=(
                    "A running service with matching startup state shows no failure "
                    "in this sample. The technician's reported symptom may come from "
                    "a dependent component or a different host."
                ),
                likelihood="medium",
                evidence_ids=[
                    ok_ids[c] for c in ("service_status", "startup_type") if c in ok_ids
                ],
            ),
            RootCause(
                title="Intermittent fault not captured by this sample",
                description=(
                    "Point-in-time status cannot rule out an intermittent fault. "
                    "Unverified without a longer observation window."
                ),
                likelihood="low",
                evidence_ids=[ok_ids[c] for c in ("event_log",) if c in ok_ids],
            ),
        ]
    else:
        causes = [
            RootCause(
                title="Service state could not be determined from the collected evidence",
                description=(
                    "No status reading is available, so no cause can be favored. "
                    "Collect a live status reading before forming hypotheses."
                ),
                likelihood="low",
                evidence_ids=[],
            ),
        ]

    usable = len(ok_ids)
    total = len(bundle.items)
    if status_value:
        summary = (
            f"Simulated assessment for '{bundle.service_name}': status "
            f"'{status_value}' from {usable} of {total} evidence items "
            f"({bundle.mode} data). Causes below are unverified hypotheses."
        )
    else:
        summary = (
            f"Simulated assessment for '{bundle.service_name}': no status reading "
            f"available ({usable} of {total} evidence items usable, {bundle.mode} "
            "data). Causes below are unverified hypotheses."
        )

    return AnalysisResult(
        summary=summary,
        facts=facts,
        causes=causes,
        uncertainties=[
            "Simulated mode: the causes above are generic hypotheses, not Meta model conclusions.",
            "The event-log sample is bounded to recent System entries; absence of entries "
            "does not prove absence of errors.",
        ],
        missing_evidence=[
            "Live service status and startup-type readings (when running on fixtures).",
            "System event-log entries covering the full failure window.",
            "Site runbook expectation for this service (expected state and startup type).",
        ],
        next_actions=[
            "Re-run the investigation with live diagnostics on the affected host.",
            "Review the full System event log around the reported failure time.",
            "Confirm the expected state and startup type for this service with the site runbook.",
            "Check dependent services and recent system changes (updates, policy, installs).",
        ],
        explanation=(
            f"FieldRook collected {total} evidence items ({bundle.mode} mode). OBSERVED "
            "facts restate those readings with evidence references. INFERRED causes are "
            "generic hypotheses consistent with the readings. UNVERIFIED items list what "
            "this sample cannot prove. No corrective action was taken and none is claimed."
        ),
        mode="simulated",
        model=SIMULATED_MODEL_NAME,
    )


def _periodic_powershell_tasks(tasks: object) -> list[tuple[str, str]]:
    """Names + repetition intervals of periodic PowerShell tasks (honest listing)."""
    found: list[tuple[str, str]] = []
    if not isinstance(tasks, list):
        return found
    for task in tasks:
        if not isinstance(task, dict):
            continue
        actions = task.get("actions", [])
        if not any(str(action.get("execute", "")).lower().endswith("powershell.exe") for action in actions if isinstance(action, dict)):
            continue
        intervals = [
            str(trigger.get("repetition_interval", ""))
            for trigger in task.get("triggers", [])
            if isinstance(trigger, dict) and trigger.get("repetition_interval")
        ]
        if intervals:
            found.append((str(task.get("task_name", "?")), intervals[0]))
    return found


def _summarize_investigation_item(item: EvidenceItem) -> str:
    data = item.data
    category = item.category
    if category == "service_status":
        return f"Service '{data.get('name', '?')}' reports status '{data.get('status', '?')}'."
    if category == "startup_type":
        return f"Startup type is '{data.get('startup_type', '?')}' (account '{data.get('start_name', '?')}')."
    if category == "event_log":
        return f"Event search examined {data.get('scanned', 0)} entries and matched {data.get('matched', 0)}."
    if category == "service_list":
        return f"Service list returned {data.get('count', 0)} entries."
    if category == "service_details":
        status = data.get("status", {})
        state = status.get("status", "?") if isinstance(status, dict) else "?"
        return f"Service '{data.get('name', '?')}' reports status '{state}'."
    if category == "os_info":
        return f"OS reports {data.get('caption', '?')}, build {data.get('build_number', '?')}."
    if category == "net_adapters":
        adapters = data.get("adapters", []) if isinstance(data.get("adapters"), list) else []
        states = ", ".join(f"{a.get('name', '?')}={a.get('status', '?')}" for a in adapters[:4])
        return f"{data.get('count', 0)} network adapters returned ({states})."
    if category == "ip_config":
        return f"{data.get('count', 0)} IP addresses configured."
    if category == "dns_config":
        return f"DNS servers reported for {data.get('count', 0)} interfaces."
    if category == "connections":
        return f"{data.get('count', 0)} established connections sampled."
    if category == "scheduled_tasks":
        base = f"{data.get('count', 0)} scheduled tasks matched (scanned {data.get('total_scanned', 0)})."
        periodic = _periodic_powershell_tasks(data.get("tasks", []))
        if periodic:
            names = ", ".join(f"{name} (every {interval})" for name, interval in periodic[:4])
            base += f" Periodic PowerShell tasks: {names}."
        return base
    if category == "demo_worker":
        return (
            f"Demo worker '{data.get('worker_id', '?')}' reports {data.get('status', '?')} "
            f"(heartbeat {data.get('heartbeat_age_s', '?')}s old)."
        )
    if category == "error_code":
        return f"Error code {data.get('hex', '?')}: {data.get('name') or 'unrecognized'}."
    if category == "app_crashes":
        crashes = data.get("crashes", [])
        if not crashes:
            return f"Crash search over {data.get('hours', '?')}h: examined {data.get('scanned', 0)} entries, no matching crashes."
        first = crashes[0]
        extra = f" (+{len(crashes) - 1} more)" if len(crashes) > 1 else ""
        return (
            f"Crash search: {data.get('matched', 0)} match(es); latest is "
            f"{first.get('app_name', '?')} ({first.get('kind', '?')} id {first.get('id', '?')}"
            f"{', module ' + first['faulting_module'] if first.get('faulting_module') else ''}"
            f"{', ' + first['exception_code'] if first.get('exception_code') else ''}){extra}."
        )
    if category == "process_info":
        service = data.get("service") or {}
        via = f" for service '{service['name']}'" if service else ""
        if not data.get("found"):
            state = f" (service state {service['state']})" if service else ""
            return f"Process lookup{via}: no matching process is running{state}."
        first = data["processes"][0]
        services = data.get("services", [])
        hosts = f", hosting {len(services)} service(s)" if services else ""
        return (
            f"Process {first.get('name', '?')} pid {first.get('pid', '?')} is running{via} "
            f"({first.get('executable_path', '?')}"
            f"{', uptime ' + str(first['uptime_s']) + 's' if first.get('uptime_s') is not None else ''}"
            f"{', ' + str(first['memory_mb']) + ' MB' if first.get('memory_mb') is not None else ''}){hosts}."
        )
    if category == "dns_test":
        if data.get("succeeded"):
            return f"DNS test: {data.get('hostname', '?')} resolves to {', '.join(data.get('addresses', []))} ({data.get('query_ms', '?')}ms)."
        return f"DNS test: {data.get('hostname', '?')} did not resolve ({data.get('error', 'unknown error')})."
    return f"Collected {category} evidence."


def _build_simulated_remote_analysis(problem: str, target: str) -> AnalysisResult:
    """Honest simulated assessment when no local measurement applies.

    Used for remote/unknown targets with no usable evidence: no causes are
    invented from thin air, and the missing evidence names what the
    technician must supply before any diagnosis is possible.
    """
    from ..schemas import AnalysisResult, ObservedFact, RootCause, RunbookStep

    short_problem = problem.strip().replace("\n", " ")[:120]
    where = "a different computer" if target == "remote" else "a computer whose identity is not established"
    steps = [
        RunbookStep(
            step="Establish which computer is affected and work from its observations.",
            why="Host measurements describe the FieldRook machine, not the affected one.",
            inspect="Whether the symptoms reproduce on this host or only on the other machine.",
            confirms="A confirmed target lets FieldRook choose applicable checks.",
            impact="read-only",
        ),
        RunbookStep(
            step="Collect the exact error text, code, and timing from the affected computer.",
            why="Exact messages decode deterministically; paraphrases do not.",
            inspect="Dialog text, event IDs, and numeric codes from the symptom report.",
            confirms="A decoded code corroborates one hypothesis over the others.",
            impact="read-only",
        ),
    ]
    return AnalysisResult(
        summary=(
            f"Simulated investigation of '{short_problem}': the affected computer is "
            f"{where}, so no host measurements were taken. No diagnosis is possible "
            "until technician-supplied observations arrive."
        ),
        facts=[
            ObservedFact(
                statement=(
                    f"No host diagnostics apply: the diagnostic target is {target}, "
                    "and host readings would describe the wrong computer."
                ),
                evidence_ids=[],
            )
        ],
        causes=[
            RootCause(
                title="No verified cause: affected-machine observations are missing",
                description=(
                    "FieldRook has no measurements from the affected computer and "
                    "refuses to guess. Supply screenshots, error codes, or manual "
                    "test results to open testable hypotheses."
                ),
                likelihood="low",
                evidence_ids=[],
            )
        ],
        uncertainties=[
            "Simulated mode: no model reasoning was applied.",
            f"Every reading so far describes the FieldRook host or nothing at all; none describes {where}.",
        ],
        missing_evidence=[
            "Which computer is affected (this host or another machine).",
            "Exact error text or code from the affected computer.",
            "Whether the symptom reproduces and when it started.",
        ],
        next_actions=[step.step for step in steps],
        next_steps=steps,
        explanation=(
            "FieldRook withheld host diagnostics because the diagnostic target is "
            f"{target}. OBSERVED facts record that decision. No INFERRED cause is "
            "offered without affected-machine evidence. The next move belongs to "
            "the technician: identify the machine and report what it shows."
        ),
        mode="simulated",
        model=SIMULATED_MODEL_NAME,
    )


def build_simulated_investigation_analysis(
    problem: str, evidence: list[EvidenceItem], target: str = "local"
) -> AnalysisResult:
    """Deterministic simulated assessment over multi-tool investigation evidence."""
    usable = [item for item in evidence if item.error is None]
    failed = [item for item in evidence if item.error is not None]
    non_local = (target or "local").strip().lower() != "local"
    if non_local and not usable:
        return _build_simulated_remote_analysis(problem, target)
    facts = [
        ObservedFact(
            statement=_summarize_investigation_item(item),
            evidence_ids=[item.id],
        )
        for item in usable[:8]
    ]
    if not facts:
        facts = [
            ObservedFact(
                statement="No usable evidence items were collected.",
                evidence_ids=[],
            )
        ]
    first_ids = [item.id for item in usable[:2]]
    short_problem = problem.strip().replace("\n", " ")[:120]
    causes = [
        RootCause(
            title="Observed state is consistent with the reported symptoms",
            description=(
                f"The collected readings may explain '{short_problem}'. This is a generic "
                "hypothesis: correlation in a small sample is not proof of cause."
            ),
            likelihood="medium",
            evidence_ids=first_ids,
        ),
        RootCause(
            title="Cause lies outside the collected evidence",
            description=(
                "The bounded, read-only sample may have missed the faulty component, the "
                "relevant log, or the failure window. Unverified without wider evidence."
            ),
            likelihood="low",
            evidence_ids=[],
        ),
    ]
    task_items = [item for item in usable if item.category == "scheduled_tasks"]
    crash_items = [item for item in usable if item.category == "app_crashes"]
    lowered_problem = problem.lower()
    popup_like = any(word in lowered_problem for word in ("popup", "pop-up", "pop up", "window", "flash", "powershell", "console", "minutes", "periodically"))
    correlated: list[tuple[str, str, str]] = []
    # Newest reading first: after a re-check, hypotheses follow current
    # evidence while historical facts stay in the record below.
    for item in reversed(crash_items):
        crashes = item.data.get("crashes", [])
        if not isinstance(crashes, list):
            continue
        for crash in crashes:
            if not isinstance(crash, dict):
                continue
            app = str(crash.get("app_name", "") or "")
            base = app.lower().removesuffix(".exe")
            if len(base) >= 3 and base in lowered_problem:
                detail = str(crash.get("exception_code", "") or crash.get("kind", "") or "")
                correlated.append((item.id, app, detail))
    if correlated:
        evidence_id, app, detail = correlated[0]
        extra = f" (+{len(correlated) - 1} more)" if len(correlated) > 1 else ""
        causes.insert(
            0,
            RootCause(
                title=f"Crash evidence names {app}",
                description=(
                    f"The crash search recorded {app} failing"
                    f"{' (' + detail + ')' if detail else ''}, which matches the "
                    "reported symptom by application name. This is correlation, not "
                    "proof of the trigger: timestamps and user actions still need "
                    "checking before concluding this record explains the report."
                    f"{extra}."
                ),
                likelihood="medium",
                evidence_ids=[evidence_id],
            ),
        )
    if popup_like and task_items:
        periodic_ids = [item.id for item in task_items if _periodic_powershell_tasks(item.data.get("tasks", []))]
        if periodic_ids:
            causes.insert(
                0,
                RootCause(
                    title="A periodic PowerShell task matches the reported cadence",
                    description=(
                        "At least one scheduled task runs PowerShell on a short repetition "
                        "interval, which is consistent with recurring console windows. This "
                        "is correlation, not proof: the task may be hidden, disabled, or "
                        "unrelated. Check trigger intervals against the symptom timing and "
                        "inspect action metadata (arguments vs working directory) before "
                        "concluding anything."
                    ),
                    likelihood="medium",
                    evidence_ids=periodic_ids,
                ),
            )
    uncertainties = [
        "Simulated mode: the causes above are generic hypotheses, not Meta model conclusions.",
        "Bounded samples cannot prove absence of failure; zero matches only mean zero matches in the examined window.",
    ]
    if non_local:
        uncertainties.insert(
            1,
            f"Diagnostic target is {target}: host measurements were withheld, so "
            "these hypotheses rest on technician-supplied observations, not "
            "independent readings from the affected computer.",
        )
    for item in task_items:
        tasks = item.data.get("tasks", [])
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            name = task.get("task_name", "?")
            for action in task.get("actions", []) or []:
                if not isinstance(action, dict):
                    continue
                workdir = str(action.get("working_directory", "") or "")
                if "windowstyle" in workdir.lower().replace(" ", "").replace("-", ""):
                    uncertainties.append(
                        f"Task '{name}' has window-hiding text inside its working directory "
                        f"({item.id}); arguments may be misplaced. Suspicious but unverified."
                    )
            if task.get("last_run_succeeded") is False and task.get("state") != "Disabled":
                uncertainties.append(
                    f"Task '{name}' reports a failing last run (result "
                    f"{task.get('last_task_result')}); decode it with interpret_error_code "
                    "instead of guessing."
                )
    uncertainties.extend(f"Evidence {item.id} ({item.category}) failed to collect: {item.error}" for item in failed[:3])
    from ..analysis.contradictions import detect_contradictions

    for hit in detect_contradictions(problem, evidence):
        uncertainties.append(f"Apparent contradiction: {hit.description}")
    from ..schemas import RunbookStep

    next_steps = [
        RunbookStep(
            step="Re-run with live diagnostics on the affected host.",
            why="Fixture readings stand in for the real host; only live collection can confirm host state.",
            inspect="Run the same investigation on the affected machine with fixtures off.",
            confirms="Live readings match the fixture pattern, or diverge and redirect the diagnosis.",
            impact="read-only",
        ),
        RunbookStep(
            step="Widen the event search to the Application log and a longer window.",
            why="The bounded sample may have missed the failure record or the relevant log.",
            inspect="Application and System logs around the reported failure time.",
            confirms="A matching error near the symptom time strengthens the cause; absence keeps it unverified.",
            impact="read-only",
        ),
        RunbookStep(
            step="Collect the exact error text or code from the reporter.",
            why="Exact messages decode deterministically; paraphrases do not.",
            inspect="Dialog text, event IDs, and numeric codes from the symptom report.",
            confirms="A decoded code corroborates one hypothesis over the others.",
            impact="read-only",
        ),
        RunbookStep(
            step="Compare against a known-good host or a prior working state.",
            why="A baseline separates broken configuration from normal-for-this-host readings.",
            inspect="Same service settings, task definitions, and adapter state on a working host.",
            confirms="Differences isolate the suspect; identical readings weaken the hypothesis.",
            impact="read-only",
        ),
    ]
    suspect_tasks = sorted({
        task.get("task_name", "?")
        for item in task_items
        for task in (item.data.get("tasks", []) if isinstance(item.data.get("tasks", []), list) else [])
        if isinstance(task, dict)
        and any(
            "windowstyle" in str(action.get("working_directory", "") or "").lower().replace(" ", "").replace("-", "")
            for action in (task.get("actions", []) or [])
            if isinstance(action, dict)
        )
    })
    if suspect_tasks:
        names = ", ".join(f"'{name}'" for name in suspect_tasks[:3])
        suspect_ids = [item.id for item in task_items if _periodic_powershell_tasks(item.data.get("tasks", []))]
        next_steps.insert(
            0,
            RunbookStep(
                step=(
                    f"Have a technician review scheduled task {names}: move the "
                    "window-hiding flag into Arguments, set a real working directory, "
                    "and re-check read-only (FieldRook cannot modify tasks)."
                ),
                why="Window-hiding text sits in WorkingDirectory instead of Arguments, so the console may show and the directory is invalid.",
                evidence_ids=suspect_ids or [item.id for item in task_items[:1]],
                inspect="Task Scheduler action Arguments versus Working Directory for the named task.",
                confirms="A corrected definition with no visible window on next run supports the misconfiguration cause.",
                impact="changes-system",
                admin_maybe=True,
            ),
        )
    next_actions = [step.step for step in next_steps]
    proposed_action = None
    failed_workers = [
        item for item in usable
        if item.category == "demo_worker" and str(item.data.get("status", "")) != "healthy"
    ]
    if failed_workers:
        from ..schemas import ProposedAction

        proposed_action = ProposedAction(
            action_id="recover_demo_worker",
            target="demo-worker",
            reason="Simulated evidence shows the demo worker is not healthy; recovery is applicable.",
            evidence_ids=[item.id for item in failed_workers],
        )
    return AnalysisResult(
        summary=(
            f"Simulated investigation of '{short_problem}': {len(usable)} of {len(evidence)} "
            "evidence items usable. Causes below are unverified hypotheses."
        ),
        facts=facts,
        causes=causes,
        uncertainties=uncertainties,
        missing_evidence=[
            "Live diagnostic readings (when running on fixtures).",
            "Full event-log history around the reported failure time.",
            "User-reported symptom details: when it started, exact messages, reproducibility.",
        ],
        next_actions=next_actions,
        next_steps=next_steps,
        explanation=(
            f"FieldRook ran a bounded read-only investigation and kept {len(usable)} usable "
            "evidence items. OBSERVED facts restate those readings. INFERRED causes are "
            "generic hypotheses. UNVERIFIED items list what the sample cannot prove. No "
            "corrective action was taken and none is claimed."
        ),
        mode="simulated",
        model=SIMULATED_MODEL_NAME,
        proposed_action=proposed_action,
    )
