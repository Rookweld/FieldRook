"""Toolpack declarations: schema validation, uniqueness, enums, family map."""

import importlib
import warnings

import pytest
from pydantic import ValidationError

from app.toolpacks.declaration import ToolDecl, ToolPackSpec, check_global_uniqueness
from app.toolpacks.families import (
    ALL_VERIFIED_TOOLS,
    DEMO_TOOLS,
    FAMILY_METADATA,
    FAMILY_TOOL_MAP,
    TOOLPACKS,
    all_mapped_tools,
    family_for_tool,
)


def _decl_dict(**overrides: object) -> dict:
    base: dict = {
        "name": "list_devices",
        "description": "List PnP devices (read-only).",
        "category": "pnp_devices",
        "args_model": "ListDevicesArgs",
        "args_schema": {"type": "object", "properties": {}},
        "impact_tier": "READ_ONLY",
        "sensitivity": "internal",
        "live_impl": "app.diagnostics.windows_devices.list_devices_live",
        "fixture_impl": "app.diagnostics.windows_devices.list_devices_fixture",
        "errors": ["COMMAND_TIMEOUT"],
    }
    base.update(overrides)
    return base


def _pack_dict(**overrides: object) -> dict:
    base: dict = {
        "toolpack_id": "devices-core",
        "pack_version": "1.0.0",
        "min_app_version": "0.1.0",
        "privileges": "current_user_readonly",
        "family": "devices",
        "tools": [_decl_dict()],
    }
    base.update(overrides)
    return base


def test_valid_decl_and_pack_pass() -> None:
    decl = ToolDecl.model_validate(_decl_dict())
    assert decl.name == "list_devices"
    assert decl.timeout_s is None
    pack = ToolPackSpec.model_validate(_pack_dict())
    assert pack.tools[0].name == "list_devices"


def test_decl_rejects_bad_name() -> None:
    for bad in ("", "Has Caps", "has-dash", "has space", "9starts_digit", "semi;colon", "x" * 65):
        with pytest.raises(ValidationError):
            ToolDecl.model_validate(_decl_dict(name=bad))


def test_decl_requires_exactly_one_readonly_or_active_marker() -> None:
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(description="No marker here."))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(description="(read-only) but also ACTIVE TEST Changes nothing."))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(description="ACTIVE TEST without the promise."))
    active = ToolDecl.model_validate(
        _decl_dict(description="ACTIVE TEST: one query. Changes nothing; labeled in provenance.")
    )
    assert active.impact_tier == "READ_ONLY"


def test_decl_rejects_bad_category_and_model() -> None:
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(category="Has Caps"))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(category=""))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(args_model="not a model!"))


def test_decl_rejects_non_object_args_schema() -> None:
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(args_schema={"type": "string"}))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(args_schema={}))


def test_decl_validates_timeout_bounds() -> None:
    assert ToolDecl.model_validate(_decl_dict(timeout_s=30.0)).timeout_s == 30.0
    for bad in (0, -1.0, 301.0):
        with pytest.raises(ValidationError):
            ToolDecl.model_validate(_decl_dict(timeout_s=bad))


def test_decl_rejects_bad_impl_and_errors() -> None:
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(live_impl="not a dotted path!"))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(fixture_impl="singleword"))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(errors=["", "  "]))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(errors=["DUP", "DUP"]))


def test_decl_rejects_unknown_enums_and_extra_keys() -> None:
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(impact_tier="SOMETHING_ELSE"))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(sensitivity="topsecret"))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate({**_decl_dict(), "unexpected": 1})


def test_pack_rejects_bad_ids_versions_enums() -> None:
    with pytest.raises(ValidationError):
        ToolPackSpec.model_validate(_pack_dict(toolpack_id="Has Caps"))
    with pytest.raises(ValidationError):
        ToolPackSpec.model_validate(_pack_dict(pack_version="1.0"))
    with pytest.raises(ValidationError):
        ToolPackSpec.model_validate(_pack_dict(min_app_version="v1"))
    with pytest.raises(ValidationError):
        ToolPackSpec.model_validate(_pack_dict(privileges="root"))
    with pytest.raises(ValidationError):
        ToolPackSpec.model_validate(_pack_dict(family="printers"))
    with pytest.raises(ValidationError):
        ToolPackSpec.model_validate(_pack_dict(tools=[]))


def test_pack_rejects_duplicate_tool_names() -> None:
    first = _decl_dict(name="same_name")
    second = _decl_dict(name="same_name", category="other_cat")
    with pytest.raises(ValidationError, match="Duplicate tool names"):
        ToolPackSpec.model_validate(_pack_dict(tools=[first, second]))


def test_global_uniqueness_across_packs() -> None:
    pack_a = ToolPackSpec.model_validate(_pack_dict(toolpack_id="pack-a"))
    pack_b = ToolPackSpec.model_validate(
        _pack_dict(toolpack_id="pack-b", family="office_local", tools=[_decl_dict(name="list_devices")])
    )
    with pytest.raises(ValueError, match="declared by both"):
        check_global_uniqueness([pack_a, pack_b])
    pack_c = ToolPackSpec.model_validate(
        _pack_dict(toolpack_id="pack-c", family="office_local", tools=[_decl_dict(name="other_tool")])
    )
    check_global_uniqueness([pack_a, pack_c])


def test_schema_version_rejects_major_warns_minor() -> None:
    with pytest.raises(ValidationError, match="major"):
        ToolDecl.model_validate(_decl_dict(schema_version="2.0"))
    with pytest.raises(ValidationError, match="major"):
        ToolPackSpec.model_validate(_pack_dict(schema_version="9.9"))
    with pytest.raises(ValidationError):
        ToolDecl.model_validate(_decl_dict(schema_version="not-a-version"))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ToolDecl.model_validate(_decl_dict(schema_version="1.1"))
    assert any("minor" in str(item.message) for item in caught)


def test_family_map_asserts_eighteen_verified_tools() -> None:
    assert FAMILY_TOOL_MAP["reliability"] == [
        "list_services",
        "get_service_details",
        "search_event_logs",
        "get_os_info",
        "get_scheduled_tasks",
        "interpret_error_code",
    ]
    assert FAMILY_TOOL_MAP["networking"] == [
        "get_network_adapters",
        "get_ip_config",
        "get_dns_config",
        "get_connections",
        "test_dns_resolution",
    ]
    assert FAMILY_TOOL_MAP["devices"] == [
        "list_devices",
        "list_volumes",
    ]
    assert FAMILY_TOOL_MAP["applications"] == [
        "search_application_crashes",
        "get_process_info",
    ]
    assert FAMILY_TOOL_MAP["office_local"] == [
        "list_office_installs",
        "get_office_config",
    ]
    assert DEMO_TOOLS == ["get_demo_worker_health"]
    assert len(all_mapped_tools()) == 17
    assert len(ALL_VERIFIED_TOOLS) == 18
    assert len(set(ALL_VERIFIED_TOOLS)) == 18
    assert set(FAMILY_METADATA) == {"reliability", "networking", "devices", "applications", "office_local"}


def test_family_lookup() -> None:
    assert family_for_tool("list_services") == "reliability"
    assert family_for_tool("test_dns_resolution") == "networking"
    assert family_for_tool("get_process_info") == "applications"
    assert family_for_tool("list_devices") == "devices"
    assert family_for_tool("get_office_config") == "office_local"
    assert family_for_tool("get_demo_worker_health") is None
    assert family_for_tool("no_such_tool") is None


def _resolve(dotted: str):  # type: ignore[no-untyped-def]
    module_name, _, func_name = dotted.rpartition(".")
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    assert callable(func)
    return func


def test_packs_reference_built_impls_only() -> None:
    assert len(TOOLPACKS) == 2
    check_global_uniqueness(TOOLPACKS)
    pack_names: list[str] = []
    for pack in TOOLPACKS:
        assert pack.privileges == "current_user_readonly"
        for tool in pack.tools:
            pack_names.append(tool.name)
            assert tool.impact_tier == "READ_ONLY"
            assert tool.timeout_s is None
            _resolve(tool.live_impl)
            _resolve(tool.fixture_impl)
    assert pack_names == ["list_devices", "list_volumes", "list_office_installs", "get_office_config"]
    assert set(pack_names) <= set(ALL_VERIFIED_TOOLS)

def test_registry_matches_family_declarations() -> None:
    """M021: REGISTRY and families are one truth (fail-closed on drift)."""
    from app.tools.registry import REGISTRY
    from app.toolpacks.families import TOOLPACKS
    assert set(REGISTRY) == set(ALL_VERIFIED_TOOLS)
    for pack in TOOLPACKS:
        for tool in pack.tools:
            spec = REGISTRY[tool.name]
            assert spec.category == tool.category
            assert family_for_tool(tool.name) == pack.family


def test_new_tools_reach_model_locally_only() -> None:
    """M021: promoted tools are offered for local targets, withheld for remote."""
    from app.analysis.loop import tools_for_target
    names = {"list_devices", "list_volumes", "list_office_installs", "get_office_config"}
    local = {(s.get("function") or {}).get("name") for s in tools_for_target("local")}
    remote = {(s.get("function") or {}).get("name") for s in tools_for_target("remote")}
    assert names <= local
    assert not (names & remote)

