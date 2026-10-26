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


def get_fixture_status(name: str) -> dict[str, str] | None:
    for service in FIXTURE_SERVICES:
        if _key(service["name"]) == _key(name):
            return dict(service)
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
        return f"{data.get('count', 0)} scheduled tasks matched (scanned {data.get('total_scanned', 0)})."
    return f"Collected {category} evidence."


def build_simulated_investigation_analysis(
    problem: str, evidence: list[EvidenceItem]
) -> AnalysisResult:
    """Deterministic simulated assessment over multi-tool investigation evidence."""
    usable = [item for item in evidence if item.error is None]
    failed = [item for item in evidence if item.error is not None]
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
    uncertainties = [
        "Simulated mode: the causes above are generic hypotheses, not Meta model conclusions.",
        "Bounded samples cannot prove absence of failure; zero matches only mean zero matches in the examined window.",
    ]
    uncertainties.extend(f"Evidence {item.id} ({item.category}) failed to collect: {item.error}" for item in failed[:3])
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
        next_actions=[
            "Re-run with live diagnostics on the affected host.",
            "Widen the event search to the Application log and a longer window.",
            "Collect the exact error text or code from the reporter.",
            "Compare against a known-good host or a prior working state.",
        ],
        explanation=(
            f"FieldRook ran a bounded read-only investigation and kept {len(usable)} usable "
            "evidence items. OBSERVED facts restate those readings. INFERRED causes are "
            "generic hypotheses. UNVERIFIED items list what the sample cannot prove. No "
            "corrective action was taken and none is claimed."
        ),
        mode="simulated",
        model=SIMULATED_MODEL_NAME,
    )
