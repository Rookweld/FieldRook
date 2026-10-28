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


def test_registry_has_eighteen_labeled_tools() -> None:
    assert len(REGISTRY) == 18
    for spec in REGISTRY.values():
        read_only = "(read-only" in spec.description
        active = "ACTIVE TEST" in spec.description
        assert read_only != active, f"{spec.name}: exactly one of read-only/ACTIVE TEST"
        if active:
            assert "Changes nothing" in spec.description


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


def test_scheduled_tasks_fixture_shape_and_redaction() -> None:
    output, _ = _run("get_scheduled_tasks", {})
    assert output.error is None
    assert output.source == "fixture"
    assert output.data["total_scanned"] == 5
    assert output.data["count"] == 4
    task = next(t for t in output.data["tasks"] if t["task_name"] == "RookweldSync")
    assert task["actions"][0]["execute"] == "powershell.exe"
    assert "[REDACTED]" in task["actions"][0]["arguments"]
    assert "abc123secret" not in task["actions"][0]["arguments"]
    assert task["principal"]["user_id"] == "<user>"
    assert task["triggers"][0]["type"] == "MSFT_TaskTimeTrigger"
    assert task["last_task_result"] == 0
    assert task["last_run_succeeded"] is True


def test_scheduled_tasks_filters() -> None:
    all_tasks, _ = _run("get_scheduled_tasks", {"include_microsoft": True})
    assert all_tasks.data["count"] == 5
    named, _ = _run("get_scheduled_tasks", {"name_contains": "rookweld"})
    assert named.data["count"] == 1
    folder, _ = _run("get_scheduled_tasks", {"folder": "\\Rookweld\\"})
    assert folder.data["count"] == 1
    limited, _ = _run("get_scheduled_tasks", {"include_microsoft": True, "limit": 2})
    assert limited.data["count"] == 2
    assert limited.data["total_scanned"] == 5


def test_scheduled_tasks_action_filter() -> None:
    output, _ = _run("get_scheduled_tasks", {"action_contains": "powershell"})
    assert output.error is None
    assert output.data["count"] == 2
    assert {t["task_name"] for t in output.data["tasks"]} == {"RookweldSync", "FieldRookDemoPhantom"}


def test_scenario_a_phantom_task_shape() -> None:
    output, _ = _run("get_scheduled_tasks", {"name_contains": "phantom"})
    assert output.error is None
    assert output.data["count"] == 1
    task = output.data["tasks"][0]
    assert task["task_path"] == "\\FieldRookDemo\\"
    assert task["triggers"][0]["repetition_interval"] == "PT5M"
    assert task["actions"][0]["execute"] == "powershell.exe"
    assert "-WindowStyle Hidden" in task["actions"][0]["working_directory"]
    assert task["last_task_result"] == 2147942667
    assert task["last_run_succeeded"] is False
    assert "Not a real system task" in task["description"]


def test_scheduled_tasks_invalid_folder_is_error_output() -> None:
    output, _ = _run("get_scheduled_tasks", {"folder": "C:\\evil"})
    assert output.error is not None


def test_task_text_sanitization() -> None:
    from app.diagnostics.windows_tasks import sanitize_task_text, truncate_arguments

    assert sanitize_task_text("run --token abc123 --x 1", None) == "run token=[REDACTED] --x 1"
    assert sanitize_task_text("password=hunter2", None) == "password=[REDACTED]"
    assert (
        sanitize_task_text("C:\\Users\\Alice\\run.ps1", "alice")
        == "C:\\Users\\<user>\\run.ps1"
    )
    assert sanitize_task_text("nothing sensitive", "alice") == "nothing sensitive"
    long_args = truncate_arguments("x" * 400)
    assert long_args.endswith("…[truncated]")
    assert truncate_arguments("short") == "short"


def test_cim_action_trigger_principal_parsing() -> None:
    from app.diagnostics.windows_tasks import (
        _ps_datetime,
        _summarize_action,
        _summarize_principal,
        _summarize_trigger,
        _task_state_name,
    )

    action = _summarize_action(
        {
            "CimInstanceProperties": [
                {"Name": "Execute", "Value": "powershell.exe"},
                {"Name": "Arguments", "Value": "-File job.ps1"},
                {"Name": "WorkingDirectory", "Value": "-WindowStyle Hidden"},
            ]
        },
        None,
    )
    assert action["execute"] == "powershell.exe"
    assert action["arguments"] == "-File job.ps1"
    assert action["working_directory"] == "-WindowStyle Hidden"

    trigger = _summarize_trigger(
        {
            "CimSystemProperties": {"ClassName": "MSFT_TaskTimeTrigger"},
            "CimInstanceProperties": [
                {"Name": "Enabled", "Value": True},
                {"Name": "StartBoundary", "Value": "2026-10-26T08:00:00"},
                {
                    "Name": "Repetition",
                    "Value": {"CimInstanceProperties": [{"Name": "Interval", "Value": "PT5M"}]},
                },
            ],
        }
    )
    assert trigger["type"] == "MSFT_TaskTimeTrigger"
    assert trigger["enabled"] is True
    assert trigger["repetition_interval"] == "PT5M"

    principal = _summarize_principal(
        {
            "CimInstanceProperties": [
                {"Name": "UserId", "Value": "Alice"},
                {"Name": "LogonType", "Value": 3},
                {"Name": "RunLevel", "Value": 0},
            ]
        },
        "alice",
    )
    assert principal["user_id"] == "<user>"
    assert principal["logon_type"] == "Interactive (3)"
    assert principal["run_level"] == "Limited (0)"

    projected = _summarize_trigger(
        {
            "Type": "MSFT_TaskTimeTrigger",
            "Enabled": True,
            "StartBoundary": "2026-10-26T08:00:00",
            "RepetitionInterval": "00:05:00",
        }
    )
    assert projected["type"] == "MSFT_TaskTimeTrigger"
    assert projected["repetition_interval"] == "00:05:00"

    assert _task_state_name(3) == "Ready"
    assert _task_state_name(1) == "Disabled"
    assert _task_state_name("Ready") == "Ready"
    assert _ps_datetime("/Date(0)/") == "1970-01-01T00:00:00Z"
    assert _ps_datetime("2026-10-26T08:00:00") == "2026-10-26T08:00:00"


def test_result_truncation_marks_oversize_data() -> None:
    small, truncated = truncate_data({"a": 1})
    assert truncated is False
    assert small == {"a": 1}
    big, was_truncated = truncate_data({"blob": "x" * (MAX_RESULT_CHARS + 100)})
    assert was_truncated is True
    assert big["_truncated"] is True
    assert len(big["preview"]) == MAX_RESULT_CHARS


def test_crash_search_fixture_shapes() -> None:
    output, _ = _run("search_application_crashes", {})
    assert output.error is None
    assert output.data["scanned"] == 5
    assert output.data["matched"] == 5
    first = output.data["crashes"][0]
    assert first["id"] == 1000
    assert first["app_name"] == "EXCEL.EXE"
    assert first["faulting_module"] == "KERNELBASE.dll"
    assert first["exception_code"] == "0xc0000005"


def test_crash_search_filters_by_app() -> None:
    output, _ = _run("search_application_crashes", {"app_name": "excel"})
    assert output.error is None
    assert output.data["matched"] == 1
    assert output.data["crashes"][0]["app_name"] == "EXCEL.EXE"
    empty, _ = _run("search_application_crashes", {"app_name": "no-such-app"})
    assert empty.error is None
    assert empty.data["matched"] == 0
    assert empty.data["scanned"] == 5


def test_crash_search_rejects_bad_app_name() -> None:
    output, _ = _run("search_application_crashes", {"app_name": "a;rm"})
    assert output.error is not None
    assert "Invalid application name" in output.error


def test_crash_search_bounded() -> None:
    output, _ = _run("search_application_crashes", {"max_events": 5})
    assert output.error is None
    assert len(output.data["crashes"]) <= 5
    with pytest.raises(ToolCallError):
        prepare_call("search_application_crashes", {"hours": 500})


def test_process_lookup_by_name_and_pid() -> None:
    by_name, _ = _run("get_process_info", {"name": "EXCEL.EXE"})
    assert by_name.error is None
    assert by_name.data["found"] is True
    assert by_name.data["processes"][0]["pid"] == 1234
    assert "CommandLine" not in str(by_name.data)
    assert "command_line" not in str(by_name.data).lower()
    by_pid, _ = _run("get_process_info", {"pid": 5678})
    assert by_pid.error is None
    assert by_pid.data["processes"][0]["name"] == "svchost.exe"
    assert by_pid.data["services"][0]["name"] == "wuauserv"


def test_process_lookup_requires_exactly_one_selector() -> None:
    neither, _ = _run("get_process_info", {})
    assert neither.error is not None
    both, _ = _run("get_process_info", {"name": "EXCEL.EXE", "pid": 1234})
    assert both.error is not None
    mixed, _ = _run("get_process_info", {"pid": 1234, "service_name": "wuauserv"})
    assert mixed.error is not None
    assert "exactly one" in mixed.error
    missing, _ = _run("get_process_info", {"name": "no-such-proc"})
    assert missing.error is None
    assert missing.data["found"] is False


def test_process_lookup_by_service_name() -> None:
    hosted, _ = _run("get_process_info", {"service_name": "wuauserv"})
    assert hosted.error is None
    assert hosted.data["found"] is True
    assert hosted.data["processes"][0]["name"] == "svchost.exe"
    assert hosted.data["service"]["name"] == "wuauserv"
    assert hosted.data["service"]["pid"] == 5678
    stopped, _ = _run("get_process_info", {"service_name": "XblGameSave"})
    assert stopped.error is None
    assert stopped.data["found"] is False
    assert stopped.data["service"]["pid"] is None
    assert "XblGameSave" in stopped.summary


def test_process_lookup_rejects_bad_service_name() -> None:
    output, _ = _run("get_process_info", {"service_name": "bad;name"})
    assert output.error is not None


def test_uptime_parses_powershell_json_dates() -> None:
    from app.diagnostics.windows_proc import _uptime_seconds

    # ConvertTo-Json shape seen on live Windows (field finding, M006).
    live = _uptime_seconds("/Date(1792040144216)/")
    assert live is not None and live > 0
    cim = _uptime_seconds("20261026081500.000000+060")
    assert cim is not None and cim > 0
    assert _uptime_seconds("") is None
    assert _uptime_seconds("not a date") is None
    assert _uptime_seconds("/Date(99999999999999)/") is None  # far future


def test_summarize_process_keeps_raw_started_without_command_line() -> None:
    from app.diagnostics.windows_proc import _summarize_process

    summary = _summarize_process(
        {
            "ProcessId": 2892,
            "Name": "svchost.exe",
            "ExecutablePath": None,
            "CreationDate": "/Date(1792040144216)/",
            "WorkingSetSize": 11639194,
        }
    )
    assert summary["pid"] == 2892
    assert summary["uptime_s"] is not None and summary["uptime_s"] > 0
    assert summary["executable_path"] == ""
    assert summary["memory_mb"] == round(11639194 / (1024 * 1024), 1)


def test_process_lookup_rejects_bad_name() -> None:
    output, _ = _run("get_process_info", {"name": "x|y"})
    assert output.error is not None


def test_dns_resolution_fixture_shapes() -> None:
    output, _ = _run("test_dns_resolution", {"hostname": "example.com"})
    assert output.error is None
    assert output.data["succeeded"] is True
    assert output.data["addresses"] == ["93.184.216.34"]
    assert "active" in output.summary
    missing, _ = _run("test_dns_resolution", {"hostname": "unknown.invalid"})
    assert missing.error is None
    assert missing.data["succeeded"] is False
    assert missing.data["error"] is not None


def test_dns_resolution_rejects_bad_hostname() -> None:
    for bad in ("has space.com", "semi;colon", "-leading.com"):
        output, _ = _run("test_dns_resolution", {"hostname": bad})
        assert output.error is not None, bad
    for bad in ("", "toolong" * 40 + ".com"):
        with pytest.raises(ToolCallError):
            prepare_call("test_dns_resolution", {"hostname": bad})


def test_service_details_include_dependencies() -> None:
    output, _ = _run("get_service_details", {"name": "wuauserv"})
    assert output.error is None
    deps = output.data["dependencies"]
    assert deps["required_services"] == ["rpcss"]
    assert deps["dependent_services"] == ["BITS"]
