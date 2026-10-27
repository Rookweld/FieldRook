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
    expect_proposal: bool = False
    forbid_proposal: bool = False
    require_uncertainty: bool = False
    must_mention_any: tuple[str, ...] = ()
    forbid_mention: tuple[str, ...] = ()
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
]


@dataclass(frozen=True)
class ToolCase:
    id: str
    tool: str
    args: dict[str, str]
    expect_error: bool
    expect_contains: dict[str, str | None]


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
]
