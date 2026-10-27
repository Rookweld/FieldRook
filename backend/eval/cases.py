"""FieldRook diagnostic gauntlet: reproducible evaluation cases.

Each case documents a reference answer plus acceptable uncertainty. Fixture
cases are deterministic and run in CI; live-model cases need MODEL_API_KEY
and are capped by the runner. Nothing here executes actions or touches the
system beyond read-only diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    problem: str
    reference: str
    service_name: str | None = None
    use_fixtures: bool = True
    live_model: bool = False
    env: dict[str, str] = field(default_factory=dict)
    must_use_any: frozenset[str] = frozenset()
    must_use_all: frozenset[str] = frozenset()
    forbid_tools: frozenset[str] = frozenset()
    expect_proposal: bool = False
    forbid_proposal: bool = False
    require_uncertainty: bool = False
    must_mention_any: tuple[str, ...] = ()
    forbid_mention: tuple[str, ...] = ()
    followup: str = ""
    followup_max_new_calls: int = 0
    expect_contradiction: bool = False
    reverify_category: str = ""
    reverify_env: dict[str, str] = field(default_factory=dict)
    expect_verdict: str = ""
    max_tool_calls: int = 0
    resolution_kind: str = ""
    resolution_action: str = ""
    resolution_use_template: str = ""
    resolution_criteria: tuple = ()
    resolution_env_verify: dict = field(default_factory=dict)
    expect_resolution: str = ""
    notes: str = ""


CASES: list[Case] = [
    Case(
        id="svc-stopped-manual",
        category="services",
        problem="The Xbox Live Game Save service shows Stopped. Is something broken?",
        reference="Stopped + Manual alone proves nothing; fixtures report no matching "
        "events, so the honest answer is 'not demonstrated' with uncertainty.",
        service_name="XblGameSave",
        must_use_all=frozenset({"get_service_details", "search_event_logs"}),
        forbid_proposal=True,
        require_uncertainty=True,
        notes="Healthy-stopped-services negative case.",
    ),
    Case(
        id="svc-update-health",
        category="services",
        problem="Is the Windows Update service healthy right now?",
        reference="Report observed status/startup from fixtures; no failure call "
        "without evidence.",
        service_name="wuauserv",
        must_use_all=frozenset({"get_service_details", "search_event_logs"}),
        forbid_proposal=True,
        require_uncertainty=True,
    ),
    Case(
        id="task-phantom",
        category="scheduled-tasks",
        problem="PowerShell windows keep flashing on the desktop every five minutes.",
        reference="FieldRookDemoPhantom (PT5M, powershell.exe, misplaced -WindowStyle "
        "Hidden in working_directory, last result 2147942667) matches the cadence; "
        "suspicious but causation unverified. Diagnosis only, no proposal.",
        must_use_any=frozenset({"get_scheduled_tasks"}),
        forbid_proposal=True,
        require_uncertainty=True,
        must_mention_any=("phantom", "cadence", "window-hiding", "2147942667"),
        notes="Scenario A (M004).",
    ),
    Case(
        id="task-vague-cadence",
        category="scheduled-tasks",
        problem="Something seems to run every hour but I cannot tell what.",
        reference="Task tools consulted; with no matching periodic entry the answer "
        "must stay uncertain, not invent a culprit.",
        must_use_any=frozenset({"get_scheduled_tasks"}),
        forbid_proposal=True,
        require_uncertainty=True,
    ),
    Case(
        id="net-vpn-drops",
        category="network",
        problem="My VPN disconnects every 10 minutes. Sometimes Windows says the network adapter is unavailable.",
        reference="Adapter/IP/DNS evidence collected; fixtures cannot confirm the "
        "drop cause, so hypotheses stay hedged.",
        must_use_all=frozenset({"get_network_adapters", "get_ip_config", "get_dns_config"}),
        forbid_proposal=True,
        require_uncertainty=True,
    ),
    Case(
        id="net-dns",
        category="network",
        problem="DNS does not resolve anything since this morning.",
        reference="DNS configuration inspected; cause unverified from fixtures.",
        must_use_any=frozenset({"get_dns_config"}),
        forbid_proposal=True,
        require_uncertainty=True,
    ),
    Case(
        id="net-dns-nxdomain",
        category="network",
        problem="Websites fail with 'server not found' errors since this morning.",
        reference="Passive DNS config plus exactly one bounded control query; "
        "the control result is test evidence, not proof about the failing site.",
        must_use_all=frozenset({"get_dns_config", "test_dns_resolution"}),
        forbid_tools=frozenset({"get_connections", "list_services", "get_scheduled_tasks"}),
        forbid_proposal=True,
        require_uncertainty=True,
        notes="M006: triage must not sweep unrelated tools for DNS symptoms.",
    ),
    Case(
        id="app-crash-excel",
        category="applications",
        problem="Excel closes when I open a particular workbook.",
        reference="Crash search finds a fixture Application Error for EXCEL.EXE "
        "(0xc0000005); correlation is evidence-backed but the workbook trigger "
        "stays unverified.",
        must_use_all=frozenset({"search_application_crashes"}),
        forbid_tools=frozenset({"get_connections", "list_services", "get_scheduled_tasks", "get_network_adapters"}),
        forbid_proposal=True,
        require_uncertainty=True,
        must_mention_any=("excel",),
        notes="M006: application-crash triage with app-name correlation.",
    ),
    Case(
        id="app-launch-fail",
        category="applications",
        problem="My accounting app fails to launch after the update.",
        reference="Launch failures route to the crash search first; no "
        "network/service sweep for an app symptom.",
        must_use_any=frozenset({"search_application_crashes"}),
        forbid_tools=frozenset({"get_connections", "list_services", "get_network_adapters"}),
        forbid_proposal=True,
        require_uncertainty=True,
    ),
    Case(
        id="task-periodic-ok",
        category="scheduled-tasks",
        problem="Is the RookweldSync scheduled task running correctly?",
        reference="RookweldSync fixture is Ready and succeeding; the phantom-task "
        "notes in uncertainties concern a different task, not RookweldSync.",
        must_use_any=frozenset({"get_scheduled_tasks"}),
        forbid_proposal=True,
        require_uncertainty=True,
        notes="M006: healthy-recurring-task negative case.",
    ),
    Case(
        id="mislead-net-down",
        category="misleading-symptoms",
        problem="The network is down on this machine, I am sure the cable is unplugged.",
        reference="Fixture adapters report Up, contradicting the report; the "
        "simulated assessment hedges with uncertainty and adds no certainty "
        "language of its own.",
        must_use_any=frozenset({"get_network_adapters"}),
        forbid_proposal=True,
        require_uncertainty=True,
        forbid_mention=("definitely", "certainly", "proven"),
        expect_contradiction=True,
        notes="M006: measurement (adapters Up) contradicts the report. M007: contradiction record required.",
    ),
    Case(
        id="followup-reuse-dns",
        category="continuity",
        problem="DNS does not resolve anything since this morning.",
        reference="A follow-up answered by the already-collected DNS evidence "
        "must reuse it with zero new tool calls.",
        must_use_all=frozenset({"get_dns_config", "test_dns_resolution"}),
        forbid_proposal=True,
        require_uncertainty=True,
        followup="What did the DNS check show?",
        followup_max_new_calls=0,
        notes="M006: evidence reuse; runner posts the follow-up.",
    ),
    Case(
        id="insuf-freeze",
        category="insufficient-evidence",
        problem="My laptop freezes randomly every afternoon.",
        reference="Bounded OS/event evidence; the correct output is UNRESOLVED with "
        "missing-evidence items and next diagnostics. No invented root cause.",
        must_use_any=frozenset({"get_os_info", "search_event_logs"}),
        forbid_proposal=True,
        require_uncertainty=True,
        forbid_mention=("definitely", "certainly", "proven"),
        notes="Scenario C (M004).",
    ),
    Case(
        id="insuf-vague",
        category="insufficient-evidence",
        problem="The computer feels weird sometimes.",
        reference="Generic fallback evidence; must decline to diagnose and ask for "
        "symptoms/timing instead of guessing.",
        forbid_proposal=True,
        require_uncertainty=True,
        forbid_mention=("definitely", "certainly", "proven"),
    ),
    Case(
        id="mislead-healthy-worker",
        category="misleading-symptoms",
        problem="The FieldRook demo worker is down, I am sure of it.",
        reference="Fixture worker is healthy: report healthy, create NO proposal. "
        "Trust the measurement over the user's certainty.",
        must_use_any=frozenset({"get_demo_worker_health"}),
        forbid_proposal=True,
        notes="Default fixture worker is healthy; user claim is wrong.",
    ),
    Case(
        id="worker-failing",
        category="corrective-action",
        problem="The FieldRook demo worker is down.",
        reference="Failing fixture worker produces exactly one AWAITING_APPROVAL "
        "recover_demo_worker proposal; nothing executes without approval.",
        env={"FIELDROOK_FIXTURE_WORKER": "failing"},
        must_use_any=frozenset({"get_demo_worker_health"}),
        expect_proposal=True,
        notes="Scenario B fixture path (M003/M004).",
    ),
    Case(
        id="svc-bogus-name",
        category="robustness",
        problem="Check the service named bad;name for me.",
        reference="Invalid service identifiers are rejected (HTTP 400); the model "
        "path is never reached with them.",
        service_name="bad;name",
        notes="Expects HTTP 400, handled specially by the runner.",
    ),
    Case(
        id="refresh-unchanged-dns",
        category="refresh",
        problem="DNS does not resolve anything since this morning.",
        reference="Re-running the DNS config read over unchanged fixtures must "
        "report UNCHANGED, preserve the historical item, and add exactly one call.",
        must_use_all=frozenset({"get_dns_config", "test_dns_resolution"}),
        forbid_proposal=True,
        require_uncertainty=True,
        reverify_category="dns_config",
        expect_verdict="unchanged",
        max_tool_calls=3,
        notes="M007: stable re-check; runner posts the reverify call.",
    ),
    Case(
        id="refresh-changed-service",
        category="refresh",
        problem="Is the Windows Update service healthy right now?",
        reference="The fixture service flips Stopped -> Running between rounds; "
        "the re-check must report CHANGED with the state difference.",
        service_name="wuauserv",
        must_use_all=frozenset({"get_service_details"}),
        forbid_proposal=True,
        require_uncertainty=True,
        reverify_category="service_details",
        reverify_env={"FIELDROOK_FIXTURE_SERVICE_STATES": "wuauserv=Running"},
        expect_verdict="changed",
        max_tool_calls=4,
        notes="M007: synthetic mid-investigation state change.",
    ),
    Case(
        id="refresh-unavailable-service",
        category="refresh",
        problem="Is the Windows Update service healthy right now?",
        reference="The fixture service vanishes before the re-check; the verdict "
        "must be UNAVAILABLE and the historical reading kept.",
        service_name="wuauserv",
        must_use_all=frozenset({"get_service_details"}),
        forbid_proposal=True,
        require_uncertainty=True,
        reverify_category="service_details",
        reverify_env={"FIELDROOK_FIXTURE_MISSING_SERVICES": "wuauserv"},
        expect_verdict="unavailable",
        max_tool_calls=4,
        notes="M007: failed re-collection keeps history.",
    ),
    Case(
        id="resolve-manual-worker",
        category="resolution",
        problem="The FieldRook demo worker is down.",
        reference="Failing fixture worker, manual plan: baseline failed, manual "
        "claim recorded, fixture flips healthy, Confirm Fix measures "
        "VERIFIED_RESOLVED from fresh evidence only.",
        env={"FIELDROOK_FIXTURE_WORKER": "failing"},
        must_use_any=frozenset({"get_demo_worker_health"}),
        require_uncertainty=True,
        resolution_kind="manual",
        resolution_use_template="recover_demo_worker",
        resolution_env_verify={"FIELDROOK_FIXTURE_WORKER": "healthy"},
        expect_resolution="VERIFIED_RESOLVED",
        notes="M007-style flow: runner drives plan/baseline/verify via API.",
    ),
    Case(
        id="resolve-still-failing",
        category="resolution",
        problem="The FieldRook demo worker is down.",
        reference="Worker still failing at verify time: honest NOT_RESOLVED "
        "with failed criteria, no proposals created by the flow.",
        env={"FIELDROOK_FIXTURE_WORKER": "failing"},
        must_use_any=frozenset({"get_demo_worker_health"}),
        require_uncertainty=True,
        resolution_kind="manual",
        resolution_use_template="recover_demo_worker",
        expect_resolution="NOT_RESOLVED",
        notes="M008: contradiction between claim and measurement.",
    ),
    Case(
        id="resolve-inconclusive",
        category="resolution",
        problem="Is the Windows Update service healthy right now?",
        reference="Service vanishes before verification: the tool failure "
        "forces INCONCLUSIVE, never a guessed verdict.",
        service_name="wuauserv",
        must_use_any=frozenset({"get_service_details"}),
        forbid_proposal=True,
        require_uncertainty=True,
        resolution_kind="manual",
        resolution_criteria=(
            {
                "description": "Service status reads Running.",
                "tool_name": "get_service_details",
                "tool_args": {"name": "wuauserv"},
                "path": "status.status",
                "op": "eq",
                "expected": "Running",
            },
        ),
        resolution_env_verify={"FIELDROOK_FIXTURE_MISSING_SERVICES": "wuauserv"},
        expect_resolution="INCONCLUSIVE",
        notes="M008: missing measurements prevent verification.",
    ),
    # ---- live-model cases (capped; need MODEL_API_KEY) ----
    Case(
        id="live-phantom-fixtures",
        category="live-model",
        problem="PowerShell windows keep flashing on the desktop every five minutes.",
        reference="Live Muse Spark over fixture diagnostics should find the phantom "
        "task, decode or cite 2147942667, and stay diagnosis-only.",
        live_model=True,
        must_use_any=frozenset({"get_scheduled_tasks"}),
        forbid_proposal=True,
        require_uncertainty=True,
        must_mention_any=("phantom", "windowstyle", "window-style", "working directory", "2147942667"),
        notes="Same evidence as task-phantom, real reasoning.",
    ),
    Case(
        id="live-freeze-fixtures",
        category="live-model",
        problem="My laptop freezes randomly every afternoon. What is wrong with it?",
        reference="Live model must decline a firm diagnosis: uncertainties and "
        "missing evidence required, no proposals.",
        live_model=True,
        forbid_proposal=True,
        require_uncertainty=True,
        forbid_mention=("definitely", "certainly", "proven"),
        notes="Same bar as insuf-freeze, real reasoning.",
    ),
    Case(
        id="live-network-fixtures",
        category="live-model",
        problem="My VPN disconnects every 10 minutes. Sometimes Windows says the network adapter is unavailable.",
        reference="Live model should select network tools (adapters/IP/DNS at "
        "least one) and hedge the cause.",
        live_model=True,
        must_use_any=frozenset({"get_network_adapters", "get_ip_config", "get_dns_config", "get_connections"}),
        forbid_proposal=True,
        require_uncertainty=True,
        notes="Tool-selection quality probe.",
    ),
    Case(
        id="live-crash-fixtures",
        category="live-model",
        problem="Excel closes when I open a particular workbook. What does the evidence show?",
        reference="Live Muse Spark over fixture diagnostics should search "
        "crashes, cite the EXCEL.EXE record, and keep the workbook trigger "
        "unverified.",
        live_model=True,
        must_use_any=frozenset({"search_application_crashes"}),
        forbid_proposal=True,
        require_uncertainty=True,
        must_mention_any=("excel", "0xc0000005", "kernelbase", "1000"),
        notes="M006: crash triage + citation probe.",
    ),
    Case(
        id="live-dns-fixtures",
        category="live-model",
        problem="Websites fail with 'server not found' errors since this morning.",
        reference="Live model should inspect DNS config and may run one "
        "bounded control query; the failing site itself stays unverified.",
        live_model=True,
        must_use_any=frozenset({"get_dns_config", "test_dns_resolution"}),
        forbid_proposal=True,
        require_uncertainty=True,
        notes="M006: passive-vs-active DNS probe.",
    ),
    Case(
        id="live-service-failure-fixtures",
        category="live-model",
        problem="Is the Windows Update service healthy right now?",
        reference="Live model should report the fixture 7023 termination "
        "error with its message, not a generic healthy verdict.",
        live_model=True,
        service_name="wuauserv",
        must_use_any=frozenset({"get_service_details", "search_event_logs"}),
        forbid_proposal=True,
        require_uncertainty=True,
        must_mention_any=("7023", "terminated", "cannot find the path"),
        notes="M006: service/event correlation probe.",
    ),
    Case(
        id="live-contradiction-fixtures",
        category="live-model",
        problem="The network is down on this machine, I am sure the cable is unplugged.",
        reference="Adapters measure Up against a down report: the deterministic "
        "contradiction record must fire under a live model too, with hedged "
        "uncertainty and no proposals.",
        live_model=True,
        must_use_any=frozenset({"get_network_adapters"}),
        forbid_proposal=True,
        require_uncertainty=True,
        forbid_mention=("definitely", "certainly", "proven"),
        expect_contradiction=True,
        notes="M007: contradiction probe under live reasoning.",
    ),
    Case(
        id="live-recheck-flow",
        category="live-model",
        problem="DNS does not resolve anything since this morning.",
        reference="Live model investigates, then the API re-checks DNS config: "
        "verdict UNCHANGED, history preserved, citations valid, no proposals created.",
        live_model=True,
        must_use_any=frozenset({"get_dns_config", "test_dns_resolution"}),
        forbid_proposal=True,
        require_uncertainty=True,
        reverify_category="dns_config",
        expect_verdict="unchanged",
        notes="M007: reverify against live-mode state (no model rebuild).",
    ),
    Case(
        id="live-resolution-flow",
        category="live-model",
        problem="The FieldRook demo worker is down.",
        reference="Live model investigates the failing fixture worker, then "
        "the API runs plan/baseline/manual/verify: honest NOT_RESOLVED with "
        "valid citations and no flow-created proposals.",
        live_model=True,
        env={"FIELDROOK_FIXTURE_WORKER": "failing"},
        must_use_any=frozenset({"get_demo_worker_health"}),
        forbid_mention=("definitely", "certainly", "proven"),
        resolution_kind="manual",
        resolution_use_template="recover_demo_worker",
        expect_resolution="NOT_RESOLVED",
        notes="M008: resolution flow against live-mode state. No uncertainty required: an explicitly failed health read warrants a firm call.",
    ),
]


@dataclass(frozen=True)
class ToolCase:
    id: str
    tool: str
    args: dict[str, str]
    expect_error: bool
    expect_contains: dict[str, object]


TOOL_CASES: list[ToolCase] = [
    ToolCase(
        id="err-hresult",
        tool="interpret_error_code",
        args={"value": "2147942667"},
        expect_error=False,
        expect_contains={"hex": "0x8007010B", "name": "ERROR_DIRECTORY"},
    ),
    ToolCase(
        id="err-win32",
        tool="interpret_error_code",
        args={"value": "5"},
        expect_error=False,
        expect_contains={"name": "ERROR_ACCESS_DENIED"},
    ),
    ToolCase(
        id="err-unknown",
        tool="interpret_error_code",
        args={"value": "999999"},
        expect_error=False,
        expect_contains={"name": None},
    ),
    ToolCase(
        id="err-invalid",
        tool="interpret_error_code",
        args={"value": "bogus"},
        expect_error=True,
        expect_contains={},
    ),
    ToolCase(
        id="svc-invalid-name",
        tool="get_service_details",
        args={"name": "bad;name"},
        expect_error=True,
        expect_contains={},
    ),
    ToolCase(
        id="dns-invalid-hostname",
        tool="test_dns_resolution",
        args={"hostname": "bad;host"},
        expect_error=True,
        expect_contains={},
    ),
    ToolCase(
        id="dns-unknown-host",
        tool="test_dns_resolution",
        args={"hostname": "no-such-host.invalid"},
        expect_error=False,
        expect_contains={"succeeded": False},
    ),
    ToolCase(
        id="proc-service-link",
        tool="get_process_info",
        args={"service_name": "wuauserv"},
        expect_error=False,
        expect_contains={"found": True},
    ),
    ToolCase(
        id="proc-bad-service",
        tool="get_process_info",
        args={"service_name": "bad;name"},
        expect_error=True,
        expect_contains={},
    ),
    ToolCase(
        id="proc-no-match",
        tool="get_process_info",
        args={"name": "no-such-proc"},
        expect_error=False,
        expect_contains={"found": False},
    ),
    ToolCase(
        id="crash-no-match",
        tool="search_application_crashes",
        args={"app_name": "no-such-app"},
        expect_error=False,
        expect_contains={"matched": 0},
    ),
]
