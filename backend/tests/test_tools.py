"""Tool registry: validation, rejection, limits, deterministic fixtures."""

import asyncio

import pytest

from app.config import Settings
from app.tools.registry import (
    MAX_RESULT_CHARS,
    REGISTRY,
    EmptyArgs,
    ToolCallError,
    ToolContext,
    ToolOutput,
    ToolSpec,
    execute_prepared,
    prepare_call,
    tool_schemas,
    truncate_data,
)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "model_api_key": None,
        "model_base_url": "https://api.meta.ai/v1",
        "model_name": "muse-spark-1.3",
        "fixtures_mode": "always",
        "command_timeout_s": 5.0,
        "model_timeout_s": 5.0,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ctx() -> ToolContext:
    return ToolContext(settings=_settings(), use_fixtures=True)


def _run(name: str, args_dict: dict) -> tuple[ToolOutput, int]:
    spec, args = prepare_call(name, args_dict)
    return asyncio.run(execute_prepared(spec, args, _ctx()))


def test_registry_has_eight_read_only_tools() -> None:
    assert len(REGISTRY) == 8
    for spec in REGISTRY.values():
        assert "(read-only" in spec.description


def test_tool_schemas_are_openai_shaped() -> None:
    for schema in tool_schemas():
        assert schema["type"] == "function"
        function = schema["function"]
        assert function["name"] and function["description"]
        assert function["parameters"]["type"] == "object"


def test_unknown_tool_rejected() -> None:
    with pytest.raises(ToolCallError):
        prepare_call("delete_everything", {})
    with pytest.raises(ToolCallError):
        prepare_call(None, {})


def test_malformed_arguments_rejected() -> None:
    with pytest.raises(ToolCallError):
        prepare_call("list_services", "not json")
    with pytest.raises(ToolCallError):
        prepare_call("list_services", {"limit": "many"})
    with pytest.raises(ToolCallError):
        prepare_call("list_services", {"limit": 9999})
    with pytest.raises(ToolCallError):
        prepare_call("list_services", {"limit": 5, "extra": 1})
    with pytest.raises(ToolCallError):
        prepare_call("list_services", ["limit"])
    with pytest.raises(ToolCallError):
        prepare_call("get_os_info", {"anything": 1})
    with pytest.raises(ToolCallError):
        prepare_call("search_event_logs", {"keywords": ""})


def test_valid_call_prepares_from_json_string() -> None:
    spec, args = prepare_call("get_service_details", '{"name": "Spooler"}')
    assert spec.name == "get_service_details"
    assert args.name == "Spooler"  # type: ignore[attr-defined]


def test_list_services_fixture_deterministic_and_capped() -> None:
    first, _ = _run("list_services", {"limit": 3})
    second, _ = _run("list_services", {"limit": 3})
    assert first.error is None
    assert first.source == "fixture"
    assert first.data["count"] == 3
    assert first.data == second.data


def test_service_details_unknown_service_is_error_output() -> None:
    output, _ = _run("get_service_details", {"name": "NoSuchSvc123"})
    assert output.error is not None
    assert output.source == "fixture"


def test_service_details_invalid_name_is_error_output() -> None:
    output, _ = _run("get_service_details", {"name": "bad;name"})
    assert output.error is not None


def test_service_details_preserves_type_fields() -> None:
    output, _ = _run("get_service_details", {"name": "Spooler"})
    assert output.error is None
    assert output.data["status"]["service_type"] == "(fixture)"
    assert output.data["status"]["service_type_value"] is None


def test_event_search_fixture_reports_stats() -> None:
    output, _ = _run("search_event_logs", {"keywords": "wuauserv"})
    assert output.error is None
    logs = output.data["logs"]
    assert logs[0]["completed"] is True
    assert logs[0]["matched"] == 2
    assert logs[0]["scanned"] > 0


def test_event_search_zero_matches_is_observation_not_failure() -> None:
    output, _ = _run("search_event_logs", {"keywords": "zz-no-such-thing-zz"})
    assert output.error is None
    assert output.data["logs"][0]["completed"] is True
    assert output.data["logs"][0]["matched"] == 0


def test_event_search_rejects_unsupported_log() -> None:
    output, _ = _run("search_event_logs", {"keywords": "x", "logs": ["Security"]})
    assert output.error is not None


def test_os_and_network_fixture_shapes() -> None:
    os_out, _ = _run("get_os_info", {})
    assert "fixture" in os_out.data["caption"]
    adapters, _ = _run("get_network_adapters", {})
    assert adapters.data["count"] == 2
    ip, _ = _run("get_ip_config", {})
    assert ip.data["count"] == 3
    dns, _ = _run("get_dns_config", {})
    assert dns.data["count"] == 2
    connections, _ = _run("get_connections", {})
    assert connections.data["count"] == 2


def test_execution_timeout_aborts_slow_tool() -> None:
    import time as time_module

    def slow_live(args: object, timeout_s: float) -> ToolOutput:
        time_module.sleep(5)
        return ToolOutput(summary="never")

    def slow_fixture(args: object) -> ToolOutput:
        time_module.sleep(5)
        return ToolOutput(summary="never")

    spec = ToolSpec(
        name="slow",
        description="test",
        category="test",
        args_model=EmptyArgs,
        run_live=slow_live,  # type: ignore[arg-type]
        run_fixture=slow_fixture,  # type: ignore[arg-type]
    )
    ctx = ToolContext(
        settings=_settings(fixtures_mode="never", command_timeout_s=0.1),
        use_fixtures=False,
    )
    output, duration_ms = asyncio.run(execute_prepared(spec, EmptyArgs(), ctx))
    assert output.error is not None
    assert "timeout" in output.error.lower()
    assert duration_ms < 3000


def test_result_truncation_marks_oversize_data() -> None:
    small, truncated = truncate_data({"a": 1})
    assert truncated is False
    assert small == {"a": 1}
    big, was_truncated = truncate_data({"blob": "x" * (MAX_RESULT_CHARS + 100)})
    assert was_truncated is True
    assert big["_truncated"] is True
    assert len(big["preview"]) == MAX_RESULT_CHARS
