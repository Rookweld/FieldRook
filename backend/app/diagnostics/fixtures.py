"""Deterministic fixture data and simulated analysis.

Fixtures stand in where real Windows diagnostics cannot run (tests, demos,
non-Windows hosts). Fixture payloads are fixed constants; only the collection
timestamps vary. Simulated analysis is derived strictly from the evidence
bundle it receives and always labels itself `simulated`.
"""

from __future__ import annotations

from ..config import SIMULATED_MODEL_NAME
from ..schemas import AnalysisResult, DiagnosticBundle, ObservedFact, RootCause

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
