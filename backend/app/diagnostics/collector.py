"""Evidence collection orchestration.

Decides between live Windows collection and deterministic fixtures, runs the
allowlisted tools, and wraps every reading in a timestamped, sourced evidence
item. Collection never modifies the system; failures are recorded as explicit
error items and warnings, never silently dropped.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import Settings
from ..schemas import DiagnosticBundle, EvidenceItem, ServiceListResponse, ServiceSummary
from . import fixtures as fx
from .event_search import search_events_live
from .service_allowlist import validate_service_name
from .windows_tools import (
    SOURCE_EVENTS,
    SOURCE_STARTUP,
    SOURCE_STATUS,
    DiagnosticCommandError,
    get_service_status,
    get_startup_type,
    list_services,
    powershell_available,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _live_event_item(name: str, display_name: str, timeout_s: float) -> EvidenceItem:
    try:
        result = search_events_live([name], ["System"], 24, 25, timeout_s)
    except (DiagnosticCommandError, ValueError) as exc:
        return EvidenceItem(
            id="ev-3",
            category="event_log",
            source=SOURCE_EVENTS,
            collected_at=_now(),
            data={},
            error=str(exc),
        )
    first = result["logs"][0]
    data = {
        "log": "System",
        "window_hours": result["window_hours"],
        "scanned": first["scanned"],
        "matched": first["matched"],
        "filter": f"entries mentioning '{name}'",
        "display_name_hint": display_name,
        "events": first["events"],
        "completed": first["completed"],
        "scan_cap": result["scan_cap"],
        "levels": result["levels"],
        "note": first["note"],
    }
    if not first["completed"]:
        return EvidenceItem(
            id="ev-3",
            category="event_log",
            source=SOURCE_EVENTS,
            collected_at=_now(),
            data=data,
            error=str(first.get("error", "Log query did not complete.")),
        )
    return EvidenceItem(
        id="ev-3",
        category="event_log",
        source=SOURCE_EVENTS,
        collected_at=_now(),
        data=data,
    )


def _collect_live(name: str, timeout_s: float) -> list[EvidenceItem]:
    try:
        status_data = get_service_status(name, timeout_s)
        status_item = EvidenceItem(
            id="ev-1",
            category="service_status",
            source=SOURCE_STATUS,
            collected_at=_now(),
            data=status_data,
        )
        display_name = str(status_data.get("display_name", ""))
    except (DiagnosticCommandError, ValueError) as exc:
        status_item = EvidenceItem(
            id="ev-1",
            category="service_status",
            source=SOURCE_STATUS,
            collected_at=_now(),
            data={},
            error=str(exc),
        )
        display_name = ""
    try:
        startup_data = get_startup_type(name, timeout_s)
        startup_item = EvidenceItem(
            id="ev-2",
            category="startup_type",
            source=SOURCE_STARTUP,
            collected_at=_now(),
            data=startup_data,
        )
    except (DiagnosticCommandError, ValueError) as exc:
        startup_item = EvidenceItem(
            id="ev-2",
            category="startup_type",
            source=SOURCE_STARTUP,
            collected_at=_now(),
            data={},
            error=str(exc),
        )
    return [status_item, startup_item, _live_event_item(name, display_name, timeout_s)]


def _live_unavailable_items() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id="ev-1",
            category="service_status",
            source=SOURCE_STATUS,
            collected_at=_now(),
            data={},
            error="Live diagnostics unavailable on this host.",
        ),
        EvidenceItem(
            id="ev-2",
            category="startup_type",
            source=SOURCE_STARTUP,
            collected_at=_now(),
            data={},
            error="Live diagnostics unavailable on this host.",
        ),
        EvidenceItem(
            id="ev-3",
            category="event_log",
            source=SOURCE_EVENTS,
            collected_at=_now(),
            data={},
            error="Live diagnostics unavailable on this host.",
        ),
    ]


def _collect_fixture(name: str, warnings: list[str]) -> list[EvidenceItem]:
    status = fx.get_fixture_status(name)
    if status is None:
        warnings.append(
            f"Service '{name}' is not in the deterministic fixture set; "
            "returning explicit no-data items."
        )
        return [
            EvidenceItem(
                id="ev-1",
                category="service_status",
                source="fixture:services",
                collected_at=_now(),
                data={},
                error=f"No fixture data for service '{name}'.",
            ),
            EvidenceItem(
                id="ev-2",
                category="startup_type",
                source="fixture:startup",
                collected_at=_now(),
                data={},
                error=f"No fixture data for service '{name}'.",
            ),
            EvidenceItem(
                id="ev-3",
                category="event_log",
                source="fixture:events",
                collected_at=_now(),
                data={},
                error=f"No fixture data for service '{name}'.",
            ),
        ]
    startup = fx.get_fixture_startup(name) or {}
    search = fx.search_fixture_events([name], ["System"], 24, 25)
    first = search["logs"][0]
    return [
        EvidenceItem(
            id="ev-1",
            category="service_status",
            source="fixture:services",
            collected_at=_now(),
            data={
                "name": status["name"],
                "display_name": status["display_name"],
                "status": status["status"],
                "service_type": "(fixture)",
                "service_type_value": None,
            },
        ),
        EvidenceItem(
            id="ev-2",
            category="startup_type",
            source="fixture:startup",
            collected_at=_now(),
            data={"name": status["name"], **startup},
        ),
        EvidenceItem(
            id="ev-3",
            category="event_log",
            source="fixture:events",
            collected_at=_now(),
            data={
                "log": "System",
                "window_hours": search["window_hours"],
                "scanned": first["scanned"],
                "matched": first["matched"],
                "filter": f"entries mentioning '{name}'",
                "display_name_hint": status["display_name"],
                "events": first["events"],
                "completed": first["completed"],
                "scan_cap": search["scan_cap"],
                "levels": search["levels"],
                "note": first["note"],
            },
        ),
    ]


def collect_diagnostics(
    service_name: str, settings: Settings, use_fixtures: bool | None = None
) -> DiagnosticBundle:
    validated = validate_service_name(service_name)
    force_fixture = settings.fixtures_mode == "always" or use_fixtures is True
    force_live = settings.fixtures_mode == "never" or use_fixtures is False
    warnings: list[str] = []
    timeout_s = settings.command_timeout_s

    if force_fixture:
        items = _collect_fixture(validated, warnings)
        mode = "fixture"
    elif not powershell_available():
        if force_live:
            warnings.append(
                "Live collection was requested but PowerShell diagnostics are "
                "unavailable on this host."
            )
            items = _live_unavailable_items()
            mode = "live"
        else:
            warnings.append(
                "Live Windows diagnostics unavailable (non-Windows host or "
                "PowerShell missing); using deterministic fixtures."
            )
            items = _collect_fixture(validated, warnings)
            mode = "fixture"
    else:
        items = _collect_live(validated, timeout_s)
        if any(item.error is None for item in items):
            mode = "live"
        elif force_live:
            warnings.append(
                "Live collection failed for every item; reporting live errors "
                "without fixture fallback."
            )
            mode = "live"
        else:
            warnings.append(
                "Live collection failed for every item; using deterministic "
                "fixtures instead."
            )
            items = _collect_fixture(validated, warnings)
            mode = "fixture"

    display_name: str | None = None
    for item in items:
        candidate = item.data.get("display_name")
        if candidate:
            display_name = str(candidate)
            break

    return DiagnosticBundle(
        service_name=validated,
        display_name=display_name,
        collected_at=_now(),
        mode=mode,  # type: ignore[arg-type]
        items=items,
        warnings=warnings,
    )


def list_services_collected(
    settings: Settings, use_fixtures: bool | None = None
) -> ServiceListResponse:
    force_fixture = settings.fixtures_mode == "always" or use_fixtures is True
    force_live = settings.fixtures_mode == "never" or use_fixtures is False
    warnings: list[str] = []

    if force_fixture or (not force_live and not powershell_available()):
        if not force_fixture:
            warnings.append(
                "Live Windows diagnostics unavailable (non-Windows host or "
                "PowerShell missing); using deterministic fixtures."
            )
        services = [ServiceSummary(**service) for service in fx.FIXTURE_SERVICES]
        return ServiceListResponse(
            services=services, mode="fixture", warnings=warnings, collected_at=_now()
        )

    try:
        raw = list_services(settings.command_timeout_s)
    except (DiagnosticCommandError, ValueError) as exc:
        if force_live:
            raise
        warnings.append(f"Live service listing failed ({exc}); using deterministic fixtures.")
        services = [ServiceSummary(**service) for service in fx.FIXTURE_SERVICES]
        return ServiceListResponse(
            services=services, mode="fixture", warnings=warnings, collected_at=_now()
        )
    services = [
        ServiceSummary(
            name=entry["name"],
            display_name=entry["display_name"] or entry["name"],
            status=entry["status"] or "Unknown",
        )
        for entry in raw
    ]
    return ServiceListResponse(
        services=services, mode="live", warnings=warnings, collected_at=_now()
    )
