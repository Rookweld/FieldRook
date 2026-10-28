"""Strict registry of read-only diagnostic tools.

The model may only request named tools with schema-validated arguments. Each
tool maps to a predefined local implementation; arbitrary commands can never
run. Every execution is bounded (timeout, result size) and audited. Tool
outputs, user descriptions, and image text are data, never instructions.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Settings
from ..diagnostics import fixtures as fx
from ..diagnostics.errorcodes import ErrorCodeError, interpret
from ..diagnostics.event_search import normalize_logs, search_events_live
from ..diagnostics.service_allowlist import validate_service_name
from ..diagnostics.windows_apps import search_crashes_live, validate_app_name
from ..diagnostics.windows_devices import (
    ListDevicesArgs,
    ListVolumesArgs,
    list_devices_fixture,
    list_devices_live,
    list_volumes_fixture,
    list_volumes_live,
)
from ..diagnostics.windows_office import (
    GetOfficeConfigArgs,
    ListOfficeInstallsArgs,
    get_office_config_fixture,
    get_office_config_live,
    list_office_installs_fixture,
    list_office_installs_live,
)
from ..diagnostics.windows_net import (
    get_adapters_live,
    get_connections_live,
    get_dns_config_live,
    get_ip_config_live,
    get_os_info_live,
    resolve_hostname_live,
    validate_hostname,
)
from ..diagnostics.windows_proc import (
    get_process_live,
    get_service_dependencies_live,
    validate_pid,
    validate_process_name,
)
from ..diagnostics.windows_tasks import (
    apply_task_filters,
    get_scheduled_tasks_live,
    sanitize_task_record,
)
from ..diagnostics.windows_tools import (
    DiagnosticCommandError,
    get_service_status,
    get_startup_type,
    list_services,
    powershell_available,
)

MAX_RESULT_CHARS = 12000


class ToolCallError(ValueError):
    """Unknown tool name or schema-invalid arguments."""


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListServicesArgs(StrictArgs):
    limit: int = Field(default=50, ge=1, le=200)


class ServiceDetailsArgs(StrictArgs):
    name: str = Field(min_length=1, max_length=64)


class EventSearchArgs(StrictArgs):
    keywords: str = Field(min_length=1, max_length=128)
    logs: list[str] = Field(default_factory=lambda: ["System"])
    hours: int = Field(default=24, ge=1, le=72)
    max_events: int = Field(default=25, ge=5, le=50)


class EmptyArgs(StrictArgs):
    pass


class AdaptersArgs(StrictArgs):
    limit: int = Field(default=16, ge=1, le=32)


class IpConfigArgs(StrictArgs):
    limit: int = Field(default=40, ge=1, le=64)


class ConnectionsArgs(StrictArgs):
    limit: int = Field(default=25, ge=1, le=50)


class ScheduledTasksArgs(StrictArgs):
    folder: str = Field(default="\\", min_length=1, max_length=128)
    name_contains: str = Field(default="", max_length=64)
    action_contains: str = Field(default="", max_length=64)
    include_microsoft: bool = False
    limit: int = Field(default=40, ge=1, le=100)


class ErrorCodeArgs(StrictArgs):
    value: str = Field(min_length=1, max_length=32)


class CrashSearchArgs(StrictArgs):
    app_name: str = Field(default="", max_length=64)
    hours: int = Field(default=24, ge=1, le=72)
    max_events: int = Field(default=15, ge=5, le=25)


class ProcessArgs(StrictArgs):
    name: str = Field(default="", max_length=64)
    pid: int = Field(default=0, ge=0, le=2_147_483_647)
    service_name: str = Field(default="", max_length=64)


class DnsResolveArgs(StrictArgs):
    hostname: str = Field(min_length=1, max_length=253)


@dataclass
class ToolContext:
    settings: Settings
    use_fixtures: bool | None = None

    @property
    def timeout_s(self) -> float:
        return self.settings.command_timeout_s

    def want_live(self) -> bool:
        if self.settings.fixtures_mode == "always" or self.use_fixtures is True:
            return False
        return True

    def allow_fixture_fallback(self) -> bool:
        if self.settings.fixtures_mode == "never" or self.use_fixtures is False:
            return False
        return True


@dataclass
class ToolOutput:
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source: str = "fixture"  # "live" | "fixture"
    error: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    category: str
    args_model: type[BaseModel]
    run_live: Callable[[BaseModel, float], ToolOutput]
    run_fixture: Callable[[BaseModel], ToolOutput]

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


def _split_keywords(raw: str) -> list[str]:
    return [part for part in re.split(r"[,\s]+", raw.strip()) if part]


# --------------------------------------------------------------------------
# Tool implementations (each raises ValueError/DiagnosticCommandError on failure;
# the runner converts failures into error outputs, never exceptions).
# --------------------------------------------------------------------------


def _list_services_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ListServicesArgs)
    services = list_services(timeout_s)[: args.limit]
    return ToolOutput(
        summary=f"Listed {len(services)} services (live).",
        data={"count": len(services), "services": services},
        source="live",
    )


def _list_services_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ListServicesArgs)
    services = [
        {"name": s["name"], "display_name": s["display_name"], "status": s["status"]}
        for s in fx.FIXTURE_SERVICES[: args.limit]
    ]
    return ToolOutput(
        summary=f"Listed {len(services)} services (fixture).",
        data={"count": len(services), "services": services},
        source="fixture",
    )


def _service_details_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ServiceDetailsArgs)
    name = validate_service_name(args.name)
    parts: dict[str, Any] = {}
    errors: list[str] = []
    try:
        parts["status"] = get_service_status(name, timeout_s)
    except (DiagnosticCommandError, ValueError) as exc:
        errors.append(f"status: {exc}")
    try:
        parts["startup"] = get_startup_type(name, timeout_s)
    except (DiagnosticCommandError, ValueError) as exc:
        errors.append(f"startup: {exc}")
    try:
        parts["events"] = search_events_live([name], ["System"], 24, 10, timeout_s)
    except (DiagnosticCommandError, ValueError) as exc:
        errors.append(f"events: {exc}")
    try:
        parts["dependencies"] = get_service_dependencies_live(name, timeout_s)
    except (DiagnosticCommandError, ValueError) as exc:
        errors.append(f"dependencies: {exc}")
    if not parts:
        return ToolOutput(
            summary=f"No details available for '{name}'.",
            error="; ".join(errors),
            source="live",
        )
    state = parts.get("status", {}).get("status", "unknown") if isinstance(parts.get("status"), dict) else "unknown"
    summary = f"Details for '{name}' (live): status {state}."
    if errors:
        summary += f" Partial failures: {'; '.join(errors)}"
    return ToolOutput(summary=summary, data={"name": name, **parts}, source="live")


def _service_details_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ServiceDetailsArgs)
    name = validate_service_name(args.name)
    raw_status = fx.get_fixture_status(name)
    if raw_status is None:
        return ToolOutput(
            summary=f"Service '{name}' is not in the fixture set.",
            error=f"No fixture data for service '{name}'.",
            source="fixture",
        )
    status = {**raw_status, "service_type": "(fixture)", "service_type_value": None}
    startup = fx.get_fixture_startup(name) or {}
    events = fx.search_fixture_events([name], ["System"], 24, 10)
    dependencies = fx.get_fixture_dependencies(name)
    return ToolOutput(
        summary=f"Details for '{status['name']}' (fixture): status {status['status']}.",
        data={
            "name": status["name"],
            "status": status,
            "startup": startup,
            "events": events,
            "dependencies": dependencies,
        },
        source="fixture",
    )


def _event_search_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, EventSearchArgs)
    keywords = _split_keywords(args.keywords)
    if not keywords:
        raise ValueError("No usable keywords.")
    logs = normalize_logs(args.logs)
    result = search_events_live(keywords, logs, args.hours, args.max_events, timeout_s)
    matched = sum(entry["matched"] for entry in result["logs"])
    scanned = sum(entry["scanned"] for entry in result["logs"])
    return ToolOutput(
        summary=f"Event search (live): examined {scanned} entries, {matched} matches.",
        data=result,
        source="live",
    )


def _event_search_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, EventSearchArgs)
    keywords = _split_keywords(args.keywords)
    if not keywords:
        raise ValueError("No usable keywords.")
    logs = normalize_logs(args.logs)
    result = fx.search_fixture_events(keywords, logs, args.hours, args.max_events)
    matched = sum(entry["matched"] for entry in result["logs"])
    scanned = sum(entry["scanned"] for entry in result["logs"])
    return ToolOutput(
        summary=f"Event search (fixture): examined {scanned} entries, {matched} matches.",
        data=result,
        source="fixture",
    )


def _os_info_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    info = get_os_info_live(timeout_s)
    return ToolOutput(
        summary=f"OS: {info.get('caption', 'unknown')} (live).", data=info, source="live"
    )


def _os_info_fixture(args: BaseModel) -> ToolOutput:
    info = fx.get_fixture_os_info()
    return ToolOutput(
        summary=f"OS: {info.get('caption', 'unknown')} (fixture).", data=info, source="fixture"
    )


def _adapters_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, AdaptersArgs)
    adapters = get_adapters_live(timeout_s, args.limit)
    return ToolOutput(
        summary=f"Found {len(adapters)} network adapters (live).",
        data={"count": len(adapters), "adapters": adapters},
        source="live",
    )


def _adapters_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, AdaptersArgs)
    adapters = fx.get_fixture_adapters()[: args.limit]
    return ToolOutput(
        summary=f"Found {len(adapters)} network adapters (fixture).",
        data={"count": len(adapters), "adapters": adapters},
        source="fixture",
    )


def _ip_config_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, IpConfigArgs)
    addresses = get_ip_config_live(timeout_s, args.limit)
    return ToolOutput(
        summary=f"Found {len(addresses)} IP addresses (live).",
        data={"count": len(addresses), "addresses": addresses},
        source="live",
    )


def _ip_config_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, IpConfigArgs)
    addresses = fx.get_fixture_ip_addresses()[: args.limit]
    return ToolOutput(
        summary=f"Found {len(addresses)} IP addresses (fixture).",
        data={"count": len(addresses), "addresses": addresses},
        source="fixture",
    )


def _dns_config_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    configs = get_dns_config_live(timeout_s)
    return ToolOutput(
        summary=f"DNS servers for {len(configs)} interfaces (live).",
        data={"count": len(configs), "interfaces": configs},
        source="live",
    )


def _dns_config_fixture(args: BaseModel) -> ToolOutput:
    configs = fx.get_fixture_dns()
    return ToolOutput(
        summary=f"DNS servers for {len(configs)} interfaces (fixture).",
        data={"count": len(configs), "interfaces": configs},
        source="fixture",
    )


def _connections_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ConnectionsArgs)
    connections = get_connections_live(timeout_s, args.limit)
    return ToolOutput(
        summary=f"Sampled {len(connections)} established connections (live).",
        data={"count": len(connections), "connections": connections},
        source="live",
    )


def _connections_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ConnectionsArgs)
    connections = fx.get_fixture_connections()[: args.limit]
    return ToolOutput(
        summary=f"Sampled {len(connections)} established connections (fixture).",
        data={"count": len(connections), "connections": connections},
        source="fixture",
    )


def _crash_search_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, CrashSearchArgs)
    app_name = validate_app_name(args.app_name)
    result = search_crashes_live(app_name, args.hours, args.max_events, timeout_s)
    if result.get("error") and not result.get("completed"):
        return ToolOutput(
            summary="Application crash search did not complete.",
            error=str(result["error"]),
            source="live",
        )
    scope = f" for '{app_name}'" if app_name else ""
    return ToolOutput(
        summary=(
            f"Crash search{scope} (live): examined {result['scanned']} entries, "
            f"{result['matched']} matches."
        ),
        data=result,
        source="live",
    )


def _crash_search_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, CrashSearchArgs)
    app_name = validate_app_name(args.app_name)
    result = fx.search_fixture_crashes(app_name, args.hours, args.max_events)
    scope = f" for '{app_name}'" if app_name else ""
    return ToolOutput(
        summary=(
            f"Crash search{scope} (fixture): examined {result['scanned']} entries, "
            f"{result['matched']} matches."
        ),
        data=result,
        source="fixture",
    )


def _process_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ProcessArgs)
    validate_process_name(args.name)
    validate_pid(args.pid)
    if (args.service_name or "").strip():
        validate_service_name(args.service_name)
    result = get_process_live(args.name, args.pid, timeout_s, args.service_name)
    service = result.get("service") or {}
    via = f" for service '{service['name']}'" if service else ""
    if not result.get("found"):
        return ToolOutput(
            summary=f"Process lookup{via} (live): no matching process is running.",
            data=result,
            source="live",
        )
    first = result["processes"][0]
    return ToolOutput(
        summary=(
            f"Process {first.get('name', '?')} pid {first.get('pid', '?')} is running "
            f"(live{via}), hosting {len(result.get('services', []))} service(s)."
        ),
        data=result,
        source="live",
    )


def _process_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ProcessArgs)
    validate_process_name(args.name)
    validate_pid(args.pid)
    if (args.service_name or "").strip():
        validate_service_name(args.service_name)
    result = fx.get_fixture_process(args.name, args.pid, args.service_name)
    service = result.get("service") or {}
    via = f" for service '{service['name']}'" if service else ""
    if not result.get("found"):
        return ToolOutput(
            summary=f"Process lookup{via} (fixture): no matching process is running.",
            data=result,
            source="fixture",
        )
    first = result["processes"][0]
    return ToolOutput(
        summary=(
            f"Process {first.get('name', '?')} pid {first.get('pid', '?')} is running "
            f"(fixture{via}), hosting {len(result.get('services', []))} service(s)."
        ),
        data=result,
        source="fixture",
    )


def _dns_resolve_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, DnsResolveArgs)
    hostname = validate_hostname(args.hostname)
    result = resolve_hostname_live(hostname, timeout_s)
    if result.get("succeeded"):
        summary = (
            f"DNS test (live, active): {hostname} resolves to "
            f"{', '.join(result['addresses'])}."
        )
    else:
        summary = f"DNS test (live, active): {hostname} did not resolve."
    return ToolOutput(summary=summary, data=result, source="live")


def _dns_resolve_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, DnsResolveArgs)
    hostname = validate_hostname(args.hostname)
    result = fx.resolve_fixture_hostname(hostname)
    if result.get("succeeded"):
        summary = (
            f"DNS test (fixture, active): {hostname} resolves to "
            f"{', '.join(result['addresses'])}."
        )
    else:
        summary = f"DNS test (fixture, active): {hostname} did not resolve."
    return ToolOutput(summary=summary, data=result, source="fixture")


def _demo_worker_health_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    from ..actions import demo_worker as worker

    health = worker.read_health()
    status = str(health.get("status", "unknown"))
    return ToolOutput(
        summary=f"Demo worker reports {status} (live).",
        data=health,
        source="live",
    )


def _demo_worker_health_fixture(args: BaseModel) -> ToolOutput:
    health = fx.get_fixture_demo_worker()
    return ToolOutput(
        summary=f"Demo worker reports {health.get('status', 'unknown')} (fixture).",
        data=health,
        source="fixture",
    )


def _decode_error_code(args: BaseModel) -> tuple[dict, str]:
    assert isinstance(args, ErrorCodeArgs)
    try:
        decoded = interpret(args.value)
    except ErrorCodeError as exc:
        raise ValueError(str(exc)) from exc
    name = decoded.get("name") or "unrecognized"
    return {k: v for k, v in decoded.items()}, f"Error code {decoded['hex']}: {name}."


def _error_code_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    data, summary = _decode_error_code(args)
    return ToolOutput(summary=summary, data=data, source="live")


def _error_code_fixture(args: BaseModel) -> ToolOutput:
    data, summary = _decode_error_code(args)
    return ToolOutput(summary=summary, data=data, source="fixture")


def _scheduled_tasks_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ScheduledTasksArgs)
    tasks = get_scheduled_tasks_live(timeout_s)
    kept, total = apply_task_filters(
        tasks,
        args.folder,
        args.name_contains,
        args.include_microsoft,
        args.limit,
        args.action_contains,
    )
    return ToolOutput(
        summary=f"Matched {len(kept)} of {total} scheduled tasks (live).",
        data={"count": len(kept), "total_scanned": total, "tasks": kept},
        source="live",
    )


def _scheduled_tasks_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ScheduledTasksArgs)
    tasks = [
        sanitize_task_record(task, fx.FIXTURE_USERNAME)
        for task in fx.get_fixture_scheduled_tasks()
    ]
    kept, total = apply_task_filters(
        tasks,
        args.folder,
        args.name_contains,
        args.include_microsoft,
        args.limit,
        args.action_contains,
    )
    return ToolOutput(
        summary=f"Matched {len(kept)} of {total} scheduled tasks (fixture).",
        data={"count": len(kept), "total_scanned": total, "tasks": kept},
        source="fixture",
    )


def _devices_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ListDevicesArgs)
    devices = list_devices_live(timeout_s, args.limit, args.status)
    problems = sum(1 for device in devices if device["has_problem"])
    return ToolOutput(
        summary=f"Listed {len(devices)} PnP devices, {problems} with problems (live).",
        data={"count": len(devices), "problems": problems, "devices": devices},
        source="live",
    )


def _devices_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ListDevicesArgs)
    devices = list_devices_fixture(args.limit, args.status)
    problems = sum(1 for device in devices if device["has_problem"])
    return ToolOutput(
        summary=f"Listed {len(devices)} PnP devices, {problems} with problems (fixture).",
        data={"count": len(devices), "problems": problems, "devices": devices},
        source="fixture",
    )


def _volumes_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ListVolumesArgs)
    volumes = list_volumes_live(timeout_s)
    return ToolOutput(
        summary=f"Listed {len(volumes)} local volumes (live).",
        data={"count": len(volumes), "volumes": volumes},
        source="live",
    )


def _volumes_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ListVolumesArgs)
    volumes = list_volumes_fixture()
    return ToolOutput(
        summary=f"Listed {len(volumes)} local volumes (fixture).",
        data={"count": len(volumes), "volumes": volumes},
        source="fixture",
    )


def _office_installs_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, ListOfficeInstallsArgs)
    installs = list_office_installs_live(timeout_s)
    return ToolOutput(
        summary=f"Listed {len(installs)} Office installs (live).",
        data={"count": len(installs), "installs": installs},
        source="live",
    )


def _office_installs_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, ListOfficeInstallsArgs)
    installs = list_office_installs_fixture()
    return ToolOutput(
        summary=f"Listed {len(installs)} Office installs (fixture).",
        data={"count": len(installs), "installs": installs},
        source="fixture",
    )


def _office_config_live(args: BaseModel, timeout_s: float) -> ToolOutput:
    assert isinstance(args, GetOfficeConfigArgs)
    config = get_office_config_live(timeout_s)
    state = "installed" if config.get("installed") else "not installed"
    return ToolOutput(
        summary=f"Office Click-to-Run {state} (live).",
        data={"config": config},
        source="live",
    )


def _office_config_fixture(args: BaseModel) -> ToolOutput:
    assert isinstance(args, GetOfficeConfigArgs)
    config = get_office_config_fixture()
    state = "installed" if config.get("installed") else "not installed"
    return ToolOutput(
        summary=f"Office Click-to-Run {state} (fixture).",
        data={"config": config},
        source="fixture",
    )


REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            name="list_services",
            description="List Windows services with their current status (read-only).",
            category="service_list",
            args_model=ListServicesArgs,
            run_live=_list_services_live,
            run_fixture=_list_services_fixture,
        ),
        ToolSpec(
            name="get_service_details",
            description="Read one service's status, startup configuration, and related "
            "System event entries (read-only).",
            category="service_details",
            args_model=ServiceDetailsArgs,
            run_live=_service_details_live,
            run_fixture=_service_details_fixture,
        ),
        ToolSpec(
            name="search_event_logs",
            description="Search System and/or Application event logs for keyword matches "
            "in recent error/warning entries (read-only, bounded).",
            category="event_log",
            args_model=EventSearchArgs,
            run_live=_event_search_live,
            run_fixture=_event_search_fixture,
        ),
        ToolSpec(
            name="get_os_info",
            description="Read basic operating system information: edition, version, build, "
            "last boot time (read-only).",
            category="os_info",
            args_model=EmptyArgs,
            run_live=_os_info_live,
            run_fixture=_os_info_fixture,
        ),
        ToolSpec(
            name="get_network_adapters",
            description="Read network adapter status, link speed, and MAC addresses "
            "(read-only).",
            category="net_adapters",
            args_model=AdaptersArgs,
            run_live=_adapters_live,
            run_fixture=_adapters_fixture,
        ),
        ToolSpec(
            name="get_ip_config",
            description="Read configured IP addresses per interface (read-only).",
            category="ip_config",
            args_model=IpConfigArgs,
            run_live=_ip_config_live,
            run_fixture=_ip_config_fixture,
        ),
        ToolSpec(
            name="get_dns_config",
            description="Read configured DNS servers per interface (read-only).",
            category="dns_config",
            args_model=EmptyArgs,
            run_live=_dns_config_live,
            run_fixture=_dns_config_fixture,
        ),
        ToolSpec(
            name="get_connections",
            description="Sample currently established TCP connections: local and remote "
            "addresses and ports (read-only, bounded).",
            category="connections",
            args_model=ConnectionsArgs,
            run_live=_connections_live,
            run_fixture=_connections_fixture,
        ),
        ToolSpec(
            name="get_demo_worker_health",
            description="Read the application-owned FieldRook demo worker health: status, "
            "heartbeat freshness, and verified process state (read-only).",
            category="demo_worker",
            args_model=EmptyArgs,
            run_live=_demo_worker_health_live,
            run_fixture=_demo_worker_health_fixture,
        ),
        ToolSpec(
            name="interpret_error_code",
            description="Deterministically decode a Windows error code (decimal, hex "
            "with or without a 0x prefix as spelled in event logs, or signed "
            "32-bit) into hex, family, and symbolic name when known (read-only "
            "computation). Never guesses unknown codes.",
            category="error_code",
            args_model=ErrorCodeArgs,
            run_live=_error_code_live,
            run_fixture=_error_code_fixture,
        ),
        ToolSpec(
            name="search_application_crashes",
            description="Search the Application log for crash/hang evidence: Application "
            "Error (1000), Error Reporting (1001), Application Hang (1002), .NET "
            "Runtime (1026), with faulting app/module, exception codes, and "
            "timestamps (read-only, bounded). Never reads dumps or user files.",
            category="app_crashes",
            args_model=CrashSearchArgs,
            run_live=_crash_search_live,
            run_fixture=_crash_search_fixture,
        ),
        ToolSpec(
            name="get_process_info",
            description="Read one process by name, pid, or hosting service name "
            "(exactly one selector): executable path, start time, uptime, memory, "
            "and services hosted in it (read-only). Full command lines are never "
            "collected.",
            category="process_info",
            args_model=ProcessArgs,
            run_live=_process_live,
            run_fixture=_process_fixture,
        ),
        ToolSpec(
            name="test_dns_resolution",
            description="ACTIVE TEST: send one A/AAAA DNS query for a validated "
            "hostname and report addresses and query time. Changes nothing; "
            "labeled as an active test in provenance.",
            category="dns_test",
            args_model=DnsResolveArgs,
            run_live=_dns_resolve_live,
            run_fixture=_dns_resolve_fixture,
        ),
        ToolSpec(
            name="get_scheduled_tasks",
            description="List Windows Scheduled Tasks with triggers, actions, principals, "
            "and last-run results (read-only). Filters: folder prefix, task-name "
            "substring, action substring (executable/arguments, e.g. powershell.exe), "
            "Microsoft-task exclusion. Arguments are truncated and secret-like "
            "values redacted.",
            category="scheduled_tasks",
            args_model=ScheduledTasksArgs,
            run_live=_scheduled_tasks_live,
            run_fixture=_scheduled_tasks_fixture,
        ),
        ToolSpec(
            name="list_devices",
            description="List PnP devices with status and problem codes (read-only, bounded).",
            category="pnp_devices",
            args_model=ListDevicesArgs,
            run_live=_devices_live,
            run_fixture=_devices_fixture,
        ),
        ToolSpec(
            name="list_volumes",
            description="List local disk volumes with size and free space (read-only).",
            category="volumes",
            args_model=ListVolumesArgs,
            run_live=_volumes_live,
            run_fixture=_volumes_fixture,
        ),
        ToolSpec(
            name="list_office_installs",
            description="List installed Office products from the uninstall registry (read-only).",
            category="office_installs",
            args_model=ListOfficeInstallsArgs,
            run_live=_office_installs_live,
            run_fixture=_office_installs_fixture,
        ),
        ToolSpec(
            name="get_office_config",
            description="Read the Office Click-to-Run version and channel (read-only).",
            category="office_config",
            args_model=GetOfficeConfigArgs,
            run_live=_office_config_live,
            run_fixture=_office_config_fixture,
        ),
    ]
}


def tool_schemas() -> list[dict[str, Any]]:
    return [spec.openai_schema() for spec in REGISTRY.values()]


def prepare_call(name: object, raw_args: object) -> tuple[ToolSpec, BaseModel]:
    """Validate a tool call. Raises ToolCallError for unknown tools or bad arguments."""
    if not isinstance(name, str) or name not in REGISTRY:
        raise ToolCallError(f"Unknown tool: {name!r}.")
    spec = REGISTRY[name]
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args or "{}")
        except json.JSONDecodeError as exc:
            raise ToolCallError(f"Tool arguments are not valid JSON: {exc}") from exc
    elif isinstance(raw_args, dict):
        parsed = raw_args
    else:
        raise ToolCallError(
            f"Tool arguments must be a JSON object, got {type(raw_args).__name__}."
        )
    try:
        args = spec.args_model.model_validate(parsed)
    except ValidationError as exc:
        raise ToolCallError(f"Invalid arguments for '{name}': {exc}") from exc
    return spec, args


def truncate_data(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    text = json.dumps(data, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return data, False
    return (
        {
            "_truncated": True,
            "total_chars": len(text),
            "preview_chars": MAX_RESULT_CHARS,
            "preview": text[:MAX_RESULT_CHARS],
        },
        True,
    )


def _run_with_fallback(spec: ToolSpec, args: BaseModel, ctx: ToolContext) -> ToolOutput:
    want_live = ctx.want_live()
    live_possible = want_live and powershell_available()
    if live_possible:
        try:
            return spec.run_live(args, ctx.timeout_s)
        except (DiagnosticCommandError, ValueError) as exc:
            if not ctx.allow_fixture_fallback():
                return ToolOutput(
                    summary=f"Tool '{spec.name}' failed.",
                    error=str(exc),
                    source="live",
                )
            try:
                output = spec.run_fixture(args)
            except (DiagnosticCommandError, ValueError) as exc2:
                return ToolOutput(
                    summary=f"Tool '{spec.name}' failed.",
                    error=str(exc2),
                    source="fixture",
                )
            output.warnings.insert(
                0, f"Live execution failed ({exc}); used deterministic fixtures."
            )
            return output
    try:
        output = spec.run_fixture(args)
    except (DiagnosticCommandError, ValueError) as exc:
        return ToolOutput(
            summary=f"Tool '{spec.name}' failed.", error=str(exc), source="fixture"
        )
    if want_live and not powershell_available():
        output.warnings.insert(
            0, "Live diagnostics unavailable on this host; used deterministic fixtures."
        )
    return output


async def execute_prepared(
    spec: ToolSpec, args: BaseModel, ctx: ToolContext
) -> tuple[ToolOutput, int]:
    """Execute a validated tool call with timeout and result-size enforcement."""
    started = time.monotonic()
    try:
        output = await asyncio.wait_for(
            asyncio.to_thread(_run_with_fallback, spec, args, ctx),
            timeout=ctx.timeout_s,
        )
    except asyncio.TimeoutError:
        output = ToolOutput(
            summary=f"Tool '{spec.name}' timed out.",
            error=f"Exceeded the {ctx.timeout_s:g}s execution timeout.",
        )
    duration_ms = int((time.monotonic() - started) * 1000)
    data, was_truncated = truncate_data(output.data)
    output.data = data
    if was_truncated:
        output.warnings.append(
            f"Result exceeded {MAX_RESULT_CHARS} characters and was truncated."
        )
    return output, duration_ms
