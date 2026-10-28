"""Family metadata and tool maps (forge.toolpack/v1, section 3 + D6).

FAMILY_TOOL_MAP covers exactly the 14 VERIFIED registry tools: 13 mapped
into reliability/networking/applications plus get_demo_worker_health outside
families. devices and office_local are new families with no verified tools
yet (NONE). PROPOSED_TOOLPACKS declares the 4 NEW BETA tools (built in
windows_devices.py / windows_office.py) for lead wiring; every proposed
tool has a live+fixture impl pair, so no unbuilt tool is contracted.
"""

from __future__ import annotations

from ..diagnostics.windows_devices import ListDevicesArgs, ListVolumesArgs
from ..diagnostics.windows_office import GetOfficeConfigArgs, ListOfficeInstallsArgs
from .declaration import ToolDecl, ToolPackSpec, check_global_uniqueness

FAMILY_METADATA: dict[str, dict[str, str]] = {
    "reliability": {
        "display_name": "Reliability",
        "description": "Services, OS, events, tasks, and error codes (read-only).",
    },
    "networking": {
        "display_name": "Networking",
        "description": "Adapters, IP/DNS config, connections, and one active DNS test.",
    },
    "devices": {
        "display_name": "Devices",
        "description": "PnP devices and volumes (new family; proposed tools await wiring).",
    },
    "applications": {
        "display_name": "Applications",
        "description": "Application crashes and process info (read-only).",
    },
    "office_local": {
        "display_name": "Office (local)",
        "description": "Local Office install metadata only, never user content (new family).",
    },
}

FAMILY_TOOL_MAP: dict[str, list[str]] = {
    "reliability": [
        "list_services",
        "get_service_details",
        "search_event_logs",
        "get_os_info",
        "get_scheduled_tasks",
        "interpret_error_code",
    ],
    "networking": [
        "get_network_adapters",
        "get_ip_config",
        "get_dns_config",
        "get_connections",
        "test_dns_resolution",
    ],
    "devices": [],
    "applications": [
        "search_application_crashes",
        "get_process_info",
    ],
    "office_local": [],
}

DEMO_TOOLS: list[str] = ["get_demo_worker_health"]

ALL_VERIFIED_TOOLS: list[str] = [
    *[name for family in ("reliability", "networking", "devices", "applications", "office_local") for name in FAMILY_TOOL_MAP[family]],
    *DEMO_TOOLS,
]


def all_mapped_tools() -> list[str]:
    """Return the 13 family-mapped verified tool names (excludes demo)."""
    return [name for names in FAMILY_TOOL_MAP.values() for name in names]


def family_for_tool(name: str) -> str | None:
    """Return the family for a mapped tool, or None (demo/unknown stay outside)."""
    for family, names in FAMILY_TOOL_MAP.items():
        if name in names:
            return family
    return None


PROPOSED_TOOLPACKS: list[ToolPackSpec] = [
    ToolPackSpec(
        toolpack_id="devices-core",
        pack_version="1.0.0",
        min_app_version="0.1.0",
        privileges="current_user_readonly",
        family="devices",
        tools=[
            ToolDecl(
                name="list_devices",
                description="List PnP devices with status and problem codes (read-only, bounded).",
                category="pnp_devices",
                args_model="ListDevicesArgs",
                args_schema=ListDevicesArgs.model_json_schema(),
                impact_tier="READ_ONLY",
                timeout_s=None,
                sensitivity="internal",
                live_impl="app.diagnostics.windows_devices.list_devices_live",
                fixture_impl="app.diagnostics.windows_devices.list_devices_fixture",
                errors=["INVALID_STATUS_FILTER", "COMMAND_TIMEOUT", "POWERSHELL_UNAVAILABLE", "OUTPUT_PARSE_ERROR"],
            ),
            ToolDecl(
                name="list_volumes",
                description="List local disk volumes with size and free space (read-only).",
                category="volumes",
                args_model="ListVolumesArgs",
                args_schema=ListVolumesArgs.model_json_schema(),
                impact_tier="READ_ONLY",
                timeout_s=None,
                sensitivity="internal",
                live_impl="app.diagnostics.windows_devices.list_volumes_live",
                fixture_impl="app.diagnostics.windows_devices.list_volumes_fixture",
                errors=["COMMAND_TIMEOUT", "POWERSHELL_UNAVAILABLE", "OUTPUT_PARSE_ERROR"],
            ),
        ],
    ),
    ToolPackSpec(
        toolpack_id="office-local-core",
        pack_version="1.0.0",
        min_app_version="0.1.0",
        privileges="current_user_readonly",
        family="office_local",
        tools=[
            ToolDecl(
                name="list_office_installs",
                description="List installed Office products from the uninstall registry (read-only).",
                category="office_installs",
                args_model="ListOfficeInstallsArgs",
                args_schema=ListOfficeInstallsArgs.model_json_schema(),
                impact_tier="READ_ONLY",
                timeout_s=None,
                sensitivity="internal",
                live_impl="app.diagnostics.windows_office.list_office_installs_live",
                fixture_impl="app.diagnostics.windows_office.list_office_installs_fixture",
                errors=["COMMAND_TIMEOUT", "POWERSHELL_UNAVAILABLE", "OUTPUT_PARSE_ERROR"],
            ),
            ToolDecl(
                name="get_office_config",
                description="Read the Office Click-to-Run version and channel (read-only).",
                category="office_config",
                args_model="GetOfficeConfigArgs",
                args_schema=GetOfficeConfigArgs.model_json_schema(),
                impact_tier="READ_ONLY",
                timeout_s=None,
                sensitivity="internal",
                live_impl="app.diagnostics.windows_office.get_office_config_live",
                fixture_impl="app.diagnostics.windows_office.get_office_config_fixture",
                errors=["COMMAND_TIMEOUT", "POWERSHELL_UNAVAILABLE", "OUTPUT_PARSE_ERROR"],
            ),
        ],
    ),
]

check_global_uniqueness(PROPOSED_TOOLPACKS)

__all__ = [
    "ALL_VERIFIED_TOOLS",
    "DEMO_TOOLS",
    "FAMILY_METADATA",
    "FAMILY_TOOL_MAP",
    "PROPOSED_TOOLPACKS",
    "all_mapped_tools",
    "family_for_tool",
]
