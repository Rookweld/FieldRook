"""FORGE DELTA engine seam: collector + knowledge context in the turn cycle."""

import asyncio

from app.analysis import evidence_digest as ed
from app.analysis.assist import _deterministic_steps, merge_plan
from app.analysis.local_tasks import reassess_prompt
from app.analysis.loop import (
    MAX_FOLLOWUP_CALLS,
    MAX_HISTORY_CHARS,
    MAX_INITIAL_CALLS,
    MAX_INVALID_PER_ROUND,
    MAX_ROUNDS,
    MAX_TOOL_CALLS,
    _run_local_tasks,
    build_investigation_messages,
    run_rounds,
)
from app.config import Settings
from app.investigations.store import InvestigationState
from app.schemas import AnalysisResult, Hypothesis


def _settings() -> Settings:
    return Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="muse-spark-1.3",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )


def _collector_item_dict(ev_id="ev-1", package="pkg-123", version="1.2.3"):
    return {
        "id": ev_id,
        "category": "dns_config",
        "source": f"collector:{package}:full",
        "data": {
            "provenance": {
                "collector": {"package_id": package, "collector_version": version}
            }
        },
        "error": None,
        "tool_name": "get_dns_config",
    }


def test_budgets_frozen_exact() -> None:
    assert MAX_ROUNDS == 4
    assert MAX_TOOL_CALLS == 12
    assert MAX_INITIAL_CALLS == 8
    assert MAX_FOLLOWUP_CALLS == 4
    assert MAX_INVALID_PER_ROUND == 3
    assert MAX_HISTORY_CHARS == 6000


def test_collector_context_quoted_in_user_message_only() -> None:
    evidence = [
        _collector_item_dict("ev-1", "pkg-abc", "2.0.1"),
        _collector_item_dict("ev-2", "pkg-abc", "2.0.1"),
    ]
    messages = build_investigation_messages(
        "DNS fails.", None, None, None, None, "remote", evidence=evidence
    )
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert isinstance(user, str)
    assert "pkg-abc" in user and "2.0.1" in user and "dns_config" in user
    assert "quoted context" in user.lower()
    assert "pkg-abc" not in system, "collector context must never be a system instruction"


def test_knowledge_excerpts_quoted_in_user_message_only() -> None:
    excerpts = [
        {
            "doc_id": "ref-1",
            "title": "DNS troubleshooting",
            "path": "docs/dns.md",
            "span": "Check the resolver order before resetting the adapter.",
        }
    ]
    messages = build_investigation_messages(
        "DNS fails.", None, None, None, None, "local", knowledge_excerpts=excerpts
    )
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert isinstance(user, str)
    assert "Check the resolver order" in user
    assert "quoted context" in user.lower()
    assert "Check the resolver order" not in system


def test_message_builder_backward_compatible_without_forge_args() -> None:
    plain = build_investigation_messages("p", None, None, None)
    assert len(plain) == 2
    assert "Collector evidence" not in str(plain[1]["content"])
    assert "Reference excerpts" not in str(plain[1]["content"])
    empty = build_investigation_messages("p", None, None, None, None, "local", evidence=[], knowledge_excerpts=[])
    assert "Collector evidence" not in str(empty[1]["content"])


def test_evidence_digest_counts_and_truncation() -> None:
    items = [
        _collector_item_dict(f"ev-{i}", f"pkg-{i}", "9.9.9") for i in range(1, 60)
    ]
    summary = ed.summarize_collector(items)
    assert summary["count"] == 59
    assert len(summary["packages"]) == 59
    digest = ed.build_evidence_digest(items, max_chars=6000)
    assert len(digest) <= 6000
    assert "59 item(s)" in digest
    tiny = ed.build_evidence_digest(items, max_chars=120)
    assert len(tiny) <= 120


def test_evidence_digest_contradiction_pointers() -> None:
    items = [_collector_item_dict()]
    contras = [{"contradiction_id": "cx-1", "evidence_ids": ["ev-1", "ev-2"]}]
    digest = ed.build_evidence_digest(items, contradictions=contras)
    assert "cx-1" in digest and "ev-1" in digest


def test_collector_capabilities_and_fresh_detection() -> None:
    items = [_collector_item_dict("ev-1"), _collector_item_dict("ev-2")]
    caps = ed.collector_capability_ids(items)
    assert "dns_config" in caps and "get_dns_config" in caps
    assert ed.new_collector_items(items, {"ev-1"})[0]["id"] == "ev-2"
    assert ed.new_collector_items(items, {"ev-1", "ev-2"}) == []
    assert ed.new_collector_items([], set()) == []


def test_knowledge_questions_extraction() -> None:
    excerpts = [
        {"span": "x", "open_question": "Which resolver answered?"},
        {"span": "y", "question": ["Is the VPN tunnel up?", ""]},
        {"span": "z"},
    ]
    questions = ed.knowledge_questions_from(excerpts)
    assert "Which resolver answered?" in questions
    assert "Is the VPN tunnel up?" in questions


def test_format_collector_rerequest_names_capability() -> None:
    instruction, why = ed.format_collector_rerequest("DNS server list")
    assert "collector capability" in instruction.lower()
    assert "DNS server list" in instruction
    assert "re-import" in instruction
    assert why.strip()
    named, _ = ed.format_collector_rerequest("DNS server list", capability="dns_config")
    assert "dns_config" in named


def test_reassess_prompt_carries_forge_context() -> None:
    base = reassess_prompt(["H1"], "obs")
    assert "Collector capabilities" not in base
    assert "Open knowledge questions" not in base
    assert "discriminate" in base and "contradicts" in base
    carried = reassess_prompt(
        ["H1"],
        "obs",
        collector_capabilities=["dns_config"],
        knowledge_questions=["Which resolver answered?"],
    )
    assert "dns_config" in carried
    assert "Which resolver answered?" in carried
    assert "discriminate" in carried


def test_run_rounds_notes_new_collector_evidence_once() -> None:
    state = InvestigationState(
        id="inv-forge-1",
        problem="DNS fails on the branch computer.",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "DNS fails on the branch computer."}],
        target="remote",
    )
    state.hypotheses.append(Hypothesis(hypothesis_id="hyp-1", title="Resolver fault"))
    state.add_evidence(
        category="dns_config",
        source="collector:pkg-abc:full",
        data={"provenance": {"collector": {"package_id": "pkg-abc", "collector_version": "2.0.1"}}},
        tool_name="get_dns_config",
    )
    asyncio.run(run_rounds(state, _settings(), None, is_followup=False))
    assert state.assist_counters.get("collector_seen_ids") == ["ev-1"]
    assert any("New collector evidence arrived" in str(m.get("content", "")) for m in state.messages)
    assert any(r.title == "Collector evidence arrived" for r in state.activity)
    notes_before = sum(1 for r in state.activity if r.title == "Collector evidence arrived")
    asyncio.run(run_rounds(state, _settings(), None, is_followup=True))
    notes_after = sum(1 for r in state.activity if r.title == "Collector evidence arrived")
    assert notes_before == notes_after == 1, "repeat rounds must not re-note seen evidence"


def test_run_rounds_without_collector_is_quiet() -> None:
    state = InvestigationState(
        id="inv-forge-2",
        problem="Excel fails.",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "Excel fails."}],
        target="remote",
    )
    asyncio.run(run_rounds(state, _settings(), None, is_followup=False))
    assert not any(r.title == "Collector evidence arrived" for r in state.activity)
    assert state.assist_counters.get("collector_seen_ids") == []


class _CaptureProvider:
    name = "local"

    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}
        self.last_stats: dict = {}

    def capabilities(self):
        from app.analysis.provider import ProviderCapabilities

        return ProviderCapabilities(
            text=True, vision=False, tool_calling=False,
            structured_output=False, processing_location="local",
        )

    def model_label(self) -> str:
        return "local/capture"

    async def run_task(self, task, prompt, timeout_s=None, images=None, cancel_scope=None):
        self.prompts[task] = prompt
        if task == "reassess":
            return {"verdict": "Still unclear.", "weakened": [], "next_step": "Check the resolver."}, []
        return None, ["unusable"]


def test_local_reassess_receives_collector_and_knowledge() -> None:
    state = InvestigationState(
        id="inv-forge-3",
        problem="DNS fails.",
        service_name=None,
        has_image=False,
        messages=[
            {"role": "user", "content": "DNS fails."},
            {"role": "user", "content": "Technician observation: nslookup timed out."},
        ],
        target="remote",
    )
    state.hypotheses.append(Hypothesis(hypothesis_id="hyp-1", title="Resolver fault"))
    state.add_evidence(
        category="dns_config",
        source="collector:pkg-abc:full",
        data={"provenance": {"collector": {"package_id": "pkg-abc", "collector_version": "2.0.1"}}},
        tool_name="get_dns_config",
    )
    state.knowledge_excerpts = [  # type: ignore[attr-defined]
        {"title": "DNS guide", "span": "Verify the resolver order.", "open_question": "Which resolver answered?"}
    ]
    provider = _CaptureProvider()
    asyncio.run(_run_local_tasks(state, provider, _settings(), True))
    assert "reassess" in provider.prompts
    assert "dns_config" in provider.prompts["reassess"]
    assert "Which resolver answered?" in provider.prompts["reassess"]


def test_remote_missing_observation_becomes_collector_rerequest() -> None:
    from app.analysis.guidance import classify_guidance

    state = InvestigationState(
        id="inv-forge-4",
        problem="App fails on the branch computer.",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "App fails."}],
        target="remote",
    )
    state.assessment = AnalysisResult(
        summary="s",
        explanation="e",
        mode="simulated",
        model="test",
        missing_evidence=["DNS server list"],
    )
    steps = _deterministic_steps(state)
    assert steps, "missing evidence must yield a deterministic step"
    assert steps[0].kind == "TECHNICIAN_CHECK"
    assert "collector capability" in steps[0].instruction.lower()
    assert "DNS server list" in steps[0].instruction
    verdict = classify_guidance(steps[0].instruction, steps[0].why, steps[0].kind)
    assert verdict.impact in (
        "READ_ONLY", "MANUAL_INFORMATION", "SYSTEM_CHANGE",
        "PRIVILEGED_ACTION", "POTENTIALLY_DISRUPTIVE", "UNSUPPORTED_OR_UNSAFE",
    )
    merge_plan(state, 1)
    assert state.plan is not None and state.plan.steps
    assert "collector capability" in state.plan.steps[0].instruction.lower()
    assert state.plan.steps[0].guidance_impact, "merged step must be guidance-classified"


def test_local_missing_observation_keeps_plain_wording() -> None:
    state = InvestigationState(
        id="inv-forge-5",
        problem="App fails.",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "App fails."}],
        target="local",
    )
    state.assessment = AnalysisResult(
        summary="s",
        explanation="e",
        mode="simulated",
        model="test",
        missing_evidence=["DNS server list"],
    )
    steps = _deterministic_steps(state)
    assert steps
    assert steps[0].instruction.startswith("Collect or describe:")
    assert "collector" not in steps[0].instruction.lower()
