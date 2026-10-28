"""M016 adaptive investigations: providers, targets, turns, hypotheses, plans."""

import asyncio
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.analysis.assist import (
    compute_stage,
    latest_assistant_message,
    mark_hypothesis,
    merge_hypotheses,
    merge_plan,
)
from app.analysis.loop import _run_live, build_investigation_messages, tools_for_target
from app.analysis.provider import (
    LocalEndpointProvider,
    MetaModelProvider,
    ProviderCapabilities,
    SimulatedProvider,
    select_provider,
    validate_local_model_url,
)
from app.analysis.validate import ModelAnalysisError, validate_assessment_output
from app.config import Settings
from app.investigations.store import InvestigationState
from app.main import app

client = TestClient(app)


def _settings(**overrides) -> Settings:
    base = {
        "model_api_key": None,
        "model_base_url": "https://api.meta.ai/v1",
        "model_name": "muse-spark-1.3",
        "fixtures_mode": "always",
        "command_timeout_s": 5.0,
        "model_timeout_s": 5.0,
    }
    base.update(overrides)
    return Settings(**base)


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200, response.text
    return response.json()


def _turn(inv_id: str, text: str, **extra: object) -> dict:
    data: dict[str, object] = {"text": text}
    data.update(extra)
    response = client.post(f"/api/investigations/{inv_id}/turn", data=data)
    assert response.status_code == 200, response.text
    return response.json()


def _final_json(evidence_ids: list[str], **extra: object) -> str:
    payload: dict[str, object] = {
        "summary": "Test summary.",
        "facts": [{"statement": "Observed.", "evidence_ids": evidence_ids}],
        "causes": [],
        "uncertainties": [],
        "missing_evidence": [],
        "next_actions": [],
        "explanation": "Test explanation.",
    }
    payload.update(extra)
    return json.dumps(payload)


class _ScriptedProvider:
    def __init__(
        self,
        script: list[dict],
        tool_calling: bool = True,
        vision: bool = True,
    ) -> None:
        self._script = script
        self.turns = 0
        self._tool_calling = tool_calling
        self._vision = vision
        self.seen_tools: list | None = None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            text=True,
            vision=self._vision,
            tool_calling=self._tool_calling,
            structured_output=True,
            processing_location="cloud",
        )

    def model_label(self) -> str:
        return "test-model"

    async def chat(self, messages, tools=None, json_only=False, cancel_scope=None):  # noqa: ANN001, ANN002, ANN003, ANN004
        self.seen_tools = tools
        reply = self._script[min(self.turns, len(self._script) - 1)]
        self.turns += 1
        return reply


def _live_state(**overrides: object) -> InvestigationState:
    params: dict[str, object] = {
        "id": "inv-test",
        "problem": "Test problem.",
        "service_name": None,
        "has_image": False,
        "messages": [{"role": "user", "content": "Test problem."}],
    }
    params.update(overrides)
    return InvestigationState(**params)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Provider selection + local endpoint validation
# ---------------------------------------------------------------------------


def test_select_provider_matrix() -> None:
    provider, mode = select_provider(_settings())
    assert mode == "simulated"
    assert isinstance(provider, SimulatedProvider)
    provider, mode = select_provider(_settings(model_api_key="k"))
    assert mode == "live"
    assert isinstance(provider, MetaModelProvider)
    provider, mode = select_provider(_settings(model_api_key="k"), "simulated")
    assert mode == "simulated"
    provider, mode = select_provider(_settings(), "local")
    assert mode == "live"
    assert isinstance(provider, LocalEndpointProvider)


def test_select_provider_override_wins_and_invalid_falls_back() -> None:
    provider, _ = select_provider(_settings(model_provider="local"), "simulated")
    assert isinstance(provider, SimulatedProvider)
    provider, mode = select_provider(_settings(model_api_key="k"), "bogus")
    assert mode == "live"  # invalid override -> auto -> meta


def test_select_provider_meta_requires_key_and_online() -> None:
    with pytest.raises(ModelAnalysisError, match="MODEL_API_KEY"):
        select_provider(_settings(), "meta")
    with pytest.raises(ModelAnalysisError, match="FIELDROOK_OFFLINE"):
        select_provider(_settings(model_api_key="k", offline_mode=True), "meta")


def test_local_url_must_be_loopback() -> None:
    assert validate_local_model_url("http://127.0.0.1:11434/v1").endswith("/v1")
    assert "localhost" in validate_local_model_url("http://localhost:11434")
    assert "://" in validate_local_model_url("http://[::1]:11434/v1")
    with pytest.raises(ModelAnalysisError, match="not set"):
        validate_local_model_url("")
    with pytest.raises(ModelAnalysisError, match="not loopback"):
        validate_local_model_url("http://192.168.1.10:11434/v1")
    with pytest.raises(ModelAnalysisError, match="not loopback"):
        validate_local_model_url("https://models.example.com/v1")
    with pytest.raises(ModelAnalysisError, match="http or https"):
        validate_local_model_url("ftp://127.0.0.1/v1")


def test_local_provider_chat_requires_config() -> None:
    async def attempt(settings: Settings) -> None:
        await LocalEndpointProvider(settings).chat([{"role": "user", "content": "hi"}])

    with pytest.raises(ModelAnalysisError, match="FIELDROOK_LOCAL_MODEL_URL"):
        asyncio.run(attempt(_settings()))
    with pytest.raises(ModelAnalysisError, match="FIELDROOK_LOCAL_MODEL_NAME"):
        asyncio.run(attempt(_settings(local_model_url="http://127.0.0.1:11434/v1")))


def test_provider_capabilities_are_declared() -> None:
    settings = _settings()
    assert MetaModelProvider(settings).capabilities().processing_location == "cloud"
    assert MetaModelProvider(settings).capabilities().tool_calling is True
    assert SimulatedProvider(settings).capabilities().processing_location == "none"
    assert SimulatedProvider(settings).capabilities().vision is False
    local = LocalEndpointProvider(settings).capabilities()
    assert local.processing_location == "local"
    assert local.vision is False and local.tool_calling is False
    # M017: vision needs flag + evidence (profile/server); the local path
    # never uses chat tool-calling (task pipeline instead).
    flagged = LocalEndpointProvider(
        _settings(
            local_model_url="http://127.0.0.1:11434/v1",
            local_model_name="qwen3-vl:8b",
            local_model_vision=True,
            local_model_tools=True,
        )
    ).capabilities()
    assert flagged.vision is True and flagged.tool_calling is False
    novision = LocalEndpointProvider(
        _settings(local_model_name="qwen3:4b", local_model_vision=True)
    ).capabilities()
    assert novision.vision is False


def test_providers_endpoint_lists_all_three() -> None:
    body = client.get("/api/providers").json()
    assert {entry["name"] for entry in body} == {"meta", "simulated", "local"}
    simulated = next(entry for entry in body if entry["name"] == "simulated")
    assert simulated["available"] is True
    meta = next(entry for entry in body if entry["name"] == "meta")
    assert meta["available"] is False  # tests run without a key


# ---------------------------------------------------------------------------
# Adaptive assessment keys (lenient validation)
# ---------------------------------------------------------------------------


def test_suggested_keys_parsed_and_evidence_filtered() -> None:
    raw = _final_json(
        ["ev-1"],
        understanding="Reported X, observed Y.",
        hypotheses=[
            {
                "title": "H1",
                "description": "maybe",
                "status": "weakened",
                "supporting_evidence_ids": ["ev-1", "ev-99"],
                "contradicting_evidence_ids": [],
            },
            {"title": "", "description": "blank title kept, filtered later"},
            "not-an-object",
        ],
        plan={
            "steps": [
                {
                    "instruction": "Check the thing.",
                    "why": "because",
                    "kind": "AUTOMATED_READ_ONLY",
                    "tool_name": "get_os_info",
                },
                {
                    "instruction": "Run anything.",
                    "kind": "AUTOMATED_READ_ONLY",
                    "tool_name": "format_c_drive",
                },
            ]
        },
        questions=[
            {"question": "When did it start?", "why": "timing matters"},
            {"question": "Q2", "why": ""},
            {"question": "Q3 dropped by cap", "why": ""},
        ],
    )
    result = validate_assessment_output(raw, {"ev-1"}, "m", "live")
    assert result.understanding == "Reported X, observed Y."
    assert len(result.suggested_hypotheses) == 2
    assert result.suggested_hypotheses[0].supporting_evidence_ids == ["ev-1"]
    assert result.suggested_plan is not None
    assert result.suggested_plan.steps[0].tool_name == "get_os_info"
    assert result.suggested_plan.steps[1].kind == "TECHNICIAN_CHECK"
    assert result.suggested_plan.steps[1].tool_name is None
    assert len(result.suggested_questions) == 2
    assert any("unknown tool" in w for w in result.validation_warnings)
    assert any("first 2 suggested questions" in w for w in result.validation_warnings)


def test_malformed_adaptive_keys_never_sink_assessment() -> None:
    raw = _final_json(["ev-1"], hypotheses="nope", plan={"steps": "nope"}, questions="nope")
    result = validate_assessment_output(raw, {"ev-1"}, "m", "live")
    assert result.suggested_hypotheses == []
    assert result.suggested_plan is None
    assert result.suggested_questions == []
    assert len(result.validation_warnings) == 3


# ---------------------------------------------------------------------------
# Hypotheses, plans, questions, stages
# ---------------------------------------------------------------------------


def test_simulated_round_builds_assist_layer() -> None:
    body = _investigate("The demo worker is down.")
    assert body["rounds_used"] == 1
    assert body["hypotheses"], "causes must seed tracked hypotheses"
    assert all(h["history"] for h in body["hypotheses"])
    assert body["plan"] is not None
    assert body["plan"]["current_step_id"]
    assert body["stage"] in ("CLARIFYING", "PLANNING", "INVESTIGATING")
    assert body["target"] == "local"
    assert body["provider_info"]["name"] == "simulated"
    kinds = [record["kind"] for record in body["activity"]]
    assert "hypothesis" in kinds and "troubleshoot_plan" in kinds


def test_remote_target_withholds_host_tools() -> None:
    body = _investigate("Excel will not open files from Teams.", target="remote")
    assert body["target"] == "remote"
    assert body["tool_calls_used"] == 0
    assert body["evidence"] == []
    assert "no host measurements were taken" in body["assessment"]["summary"]
    assert body["stage"] == "CLARIFYING"
    assert body["plan"] is not None
    kinds = {step["kind"] for step in body["plan"]["steps"]}
    assert "AUTOMATED_READ_ONLY" not in kinds
    assert any("affected computer" in q["question"].lower() or q for q in body["questions"])


def test_unknown_target_asks_target_first() -> None:
    body = _investigate("Something is broken.", target="unknown")
    assert body["target"] == "unknown"
    assert body["questions"], "unknown target must ask a clarifying question"
    assert "affected computer" in body["questions"][0]["question"]


def test_remote_caveat_survives_technician_evidence() -> None:
    started = _investigate("Excel will not open files from Teams.", target="remote")
    body = _turn(started["investigation_id"], "Local files open fine.", kind="observation")
    uncertainties = " ".join(body["assessment"]["uncertainties"])
    assert "technician-supplied observations" in uncertainties


def test_invalid_target_and_provider_rejected() -> None:
    assert client.post("/api/investigations", data={"problem": "x", "target": "mars"}).status_code == 400
    assert client.post("/api/investigations", data={"problem": "x", "provider": "hal"}).status_code == 400


def test_error_code_triage_decodes_first() -> None:
    body = _investigate("Excel fails with 0x80070005 when opening files from Teams.")
    tools_used = {
        record["tool_name"] for record in body["activity"] if record["tool_name"]
    }
    assert "interpret_error_code" in tools_used
    decoded = [item for item in body["evidence"] if item["tool_name"] == "interpret_error_code"]
    assert decoded and decoded[0]["error"] is None


def test_tools_for_target_scoping() -> None:
    local = tools_for_target("local")
    remote = tools_for_target("remote")
    assert len(local) > len(remote) >= 1
    names = {(schema.get("function") or {}).get("name") for schema in remote}
    assert names == {"interpret_error_code"}


def test_system_prompt_carries_target_block() -> None:
    local = build_investigation_messages("p", None, None, None)[0]["content"]
    remote = build_investigation_messages("p", None, None, None, None, "remote")[0]["content"]
    assert "DIAGNOSTIC TARGET" not in local
    assert "ANOTHER COMPUTER" in remote


def test_host_tool_backstop_refuses_remote_execution() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "get_os_info", "arguments": "{}"},
                    }
                ],
            },
            {"role": "assistant", "content": _final_json([]), "tool_calls": []},
        ]
    )
    state = _live_state(target="remote")
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))
    assert state.tool_calls_made == 0
    assert state.evidence == []
    assert any(record.title.startswith("Refused host tool") for record in state.activity)
    assert state.assessment is not None and state.assessment.mode == "live"
    offered = {(schema.get("function") or {}).get("name") for schema in provider.seen_tools or []}
    assert "get_os_info" not in offered


def test_plan_only_path_for_providers_without_tools() -> None:
    provider = _ScriptedProvider(
        [{"role": "assistant", "content": _final_json([]), "tool_calls": []}],
        tool_calling=False,
    )
    state = _live_state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))
    assert any(record.title == "Plan-only model round" for record in state.activity)
    assert state.tool_calls_made == 0
    assert state.assessment is not None and state.assessment.mode == "live"


def test_vision_gate_withholds_screenshots_without_capability() -> None:
    provider = _ScriptedProvider(
        [{"role": "assistant", "content": _final_json([]), "tool_calls": []}],
        vision=False,
    )
    state = _live_state(
        has_image=True,
        messages=[
            {"role": "system", "content": "sys"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "see attached"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}},
                ],
            },
        ],
    )
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))
    assert any("cannot process images" in w for w in state.warnings)
    for message in state.messages:
        content = message.get("content")
        if isinstance(content, list):
            assert all(part.get("type") != "image_url" for part in content)


def test_assistant_message_surfaces_reasoning_not_json() -> None:
    state = _live_state(
        messages=[
            {"role": "user", "content": "p"},
            {"role": "assistant", "content": "Checking the adapters first."},
            {"role": "assistant", "content": _final_json([])},
        ]
    )
    assert latest_assistant_message(state) == "Test summary."
    state2 = _live_state(
        messages=[
            {"role": "user", "content": "p"},
            {"role": "assistant", "content": "Checking the adapters first."},
        ]
    )
    assert latest_assistant_message(state2) == "Checking the adapters first."
    assert latest_assistant_message(_live_state()) == ""


# ---------------------------------------------------------------------------
# Turns, questions, plan steps
# ---------------------------------------------------------------------------


def test_observation_turn_becomes_labeled_evidence() -> None:
    started = _investigate("Excel will not open files from Teams.", target="remote")
    inv_id = started["investigation_id"]
    body = _turn(inv_id, "Local files open fine; only Teams files fail.", kind="observation")
    assert body["rounds_used"] == 2
    assert body["stage"] == "CLARIFYING", "open questions outrank the fresh turn"
    reports = [item for item in body["evidence"] if item["category"] == "technician_report"]
    assert len(reports) == 1
    assert reports[0]["source"] == "technician:observation"
    assert "not independently measured" in reports[0]["data"]["note"]
    assert any(record["kind"] == "turn" for record in body["activity"])
    # Answering every open question moves the investigation to reassessment.
    for _ in range(5):
        open_questions = [q for q in body["questions"] if q["status"] == "open"]
        if not open_questions:
            break
        body = _turn(
            inv_id, "Answered by the technician.", kind="answer",
            question_id=open_questions[0]["question_id"],
        )
    assert not [q for q in body["questions"] if q["status"] == "open"]
    assert body["stage"] == "REASSESSING"


def test_answer_closes_question_and_never_repeats() -> None:
    started = _investigate("Something is broken.", target="unknown")
    inv_id = started["investigation_id"]
    first_id = started["questions"][0]["question_id"]
    body = _turn(inv_id, "A different laptop.", kind="answer", question_id=first_id)
    answered = next(q for q in body["questions"] if q["question_id"] == first_id)
    assert answered["status"] == "answered"
    assert answered["answer"] == "A different laptop."
    texts = [q["question"] for q in body["questions"]]
    assert len(texts) == len(set(texts)), "questions must never repeat"
    # Answering again is a conflict, unknown ids are unprocessable.
    assert (
        client.post(
            f"/api/investigations/{inv_id}/turn",
            data={"kind": "answer", "text": "again", "question_id": first_id},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/investigations/{inv_id}/turn", data={"text": "x", "question_id": "q-999"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/investigations/{inv_id}/turn", data={"kind": "nap", "text": "x"}
        ).status_code
        == 400
    )


def test_turn_text_is_redacted() -> None:
    started = _investigate("Excel will not open files from Teams.", target="remote")
    body = _turn(
        started["investigation_id"],
        "Login as CORP\\jdoe with password=hunter2 fails.",
        kind="observation",
    )
    reports = [item for item in body["evidence"] if item["category"] == "technician_report"]
    assert "hunter2" not in reports[0]["data"]["text"]
    assert "jdoe" not in reports[0]["data"]["text"]


def test_plan_step_complete_advances_current() -> None:
    started = _investigate("The demo worker is down.")
    inv_id = started["investigation_id"]
    current_id = started["plan"]["current_step_id"]
    body = client.post(
        f"/api/investigations/{inv_id}/plan/steps/{current_id}/complete",
        json={"outcome": "Worker still down; health file says failed."},
    ).json()
    done = next(s for s in body["plan"]["steps"] if s["step_id"] == current_id)
    assert done["status"] == "done"
    assert "failed" in done["outcome"]
    assert body["plan"]["current_step_id"] != current_id
    assert body["rounds_used"] == 1, "completion records; it does not burn a model round"
    again = client.post(
        f"/api/investigations/{inv_id}/plan/steps/{current_id}/complete",
        json={"outcome": "x"},
    )
    assert again.status_code == 409
    missing = client.post(
        f"/api/investigations/{inv_id}/plan/steps/step-999/complete",
        json={"outcome": "x"},
    )
    assert missing.status_code == 404


def test_impossible_steps_converge_to_blocked() -> None:
    started = _investigate("Excel will not open files from Teams.", target="remote")
    inv_id = started["investigation_id"]
    body = started
    for _ in range(10):
        open_steps = [s for s in body["plan"]["steps"] if s["status"] in ("suggested", "current")]
        if not open_steps:
            break
        response = client.post(
            f"/api/investigations/{inv_id}/plan/steps/{open_steps[0]['step_id']}/impossible",
            json={"reason": "No access to that machine."},
        )
        assert response.status_code == 200
        body = response.json()
    assert body["stage"] == "BLOCKED"
    assert body["blocked_reason"]
    assert "No access" in body["blocked_reason"]


def test_hypothesis_judgment_is_recorded_and_locked() -> None:
    started = _investigate("The demo worker is down.")
    inv_id = started["investigation_id"]
    hyp_id = started["hypotheses"][0]["hypothesis_id"]
    body = client.post(
        f"/api/investigations/{inv_id}/hypotheses/{hyp_id}/status",
        json={"status": "ruled_out", "reason": "Worker confirmed healthy on site."},
    ).json()
    hyp = next(h for h in body["hypotheses"] if h["hypothesis_id"] == hyp_id)
    assert hyp["status"] == "ruled_out"
    assert hyp["history"][-1]["reason"].startswith("Technician judgment")
    # A later round must not override the technician's judgment.
    again = _turn(inv_id, "Still down according to the user.", kind="observation")
    hyp2 = next(h for h in again["hypotheses"] if h["hypothesis_id"] == hyp_id)
    assert hyp2["status"] == "ruled_out"
    missing = client.post(
        f"/api/investigations/{inv_id}/hypotheses/hyp-999/status",
        json={"status": "ruled_out", "reason": "x"},
    )
    assert missing.status_code == 404


def test_changed_refresh_weakens_hypotheses() -> None:
    state = _live_state()
    item = state.add_evidence(category="service_status", source="tool:x:fixture", data={"a": 1})
    state.rounds_used = 1
    state.assessment = validate_assessment_output(
        _final_json([item.id], causes=[{"title": "H", "description": "d", "evidence_ids": [item.id]}]),
        {item.id},
        "m",
        "simulated",
    )
    merge_hypotheses(state, 1)
    assert state.hypotheses[0].status == "active"
    state.add_refresh(
        old_evidence_id=item.id,
        new_evidence_id="ev-2",
        tool_name="x",
        verdict="changed",
        changes=["a: 1 -> 2"],
        old_collected_at=item.collected_at,
        new_collected_at=item.collected_at,
    )
    merge_hypotheses(state, 2)
    assert state.hypotheses[0].status == "weakened"
    assert "superseded" in state.hypotheses[0].history[-1].reason


def test_mark_hypothesis_rejects_unknown() -> None:
    state = _live_state()
    assert mark_hypothesis(state, "hyp-1", "ruled_out", "r", 1) is False
    assert mark_hypothesis(state, "hyp-1", "bogus", "r", 1) is False


def test_plan_merge_preserves_terminal_steps() -> None:
    state = _live_state()
    state.assessment = validate_assessment_output(
        _final_json([], missing_evidence=["A live reading."]), set(), "m", "simulated"
    )
    merge_plan(state, 1)
    first_id = state.plan.current_step_id if state.plan else None
    assert first_id
    step = next(s for s in state.plan.steps if s.step_id == first_id)
    step.status = "done"
    step.outcome = "did it"
    merge_plan(state, 2)
    assert state.plan is not None
    kept = next(s for s in state.plan.steps if s.step_id == first_id)
    assert kept.status == "done" and kept.outcome == "did it"
    assert state.plan.current_step_id != first_id


def test_compute_stage_lifecycle() -> None:
    assert compute_stage(_live_state()) == "INTAKE"
    answered_state = _live_state()
    answered_state.assessment = validate_assessment_output(
        _final_json([]), set(), "m", "simulated"
    )
    from app.schemas import ClarifyingQuestion, TroubleshootPlan

    answered_state.questions.append(
        ClarifyingQuestion(question_id="q-1", question="Q?", status="open")
    )
    assert compute_stage(answered_state) == "CLARIFYING"
    answered_state.questions[0].status = "answered"
    answered_state.plan = TroubleshootPlan(plan_id="tplan-x")
    assert compute_stage(answered_state) == "PLANNING"
    answered_state.blocked_reason = "stuck"
    assert compute_stage(answered_state) == "BLOCKED"


# ---------------------------------------------------------------------------
# Provider switching, targets, screenshots, persistence
# ---------------------------------------------------------------------------


def test_provider_switch_requires_cloud_confirmation() -> None:
    started = _investigate("The demo worker is down.")
    inv_id = started["investigation_id"]
    denied = client.post(
        f"/api/investigations/{inv_id}/provider", json={"provider": "meta"}
    )
    assert denied.status_code == 400
    assert "confirm_cloud" in denied.text
    # Switching to local/simulated needs no confirmation and keeps evidence.
    body = client.post(
        f"/api/investigations/{inv_id}/provider", json={"provider": "local"}
    ).json()
    assert body["provider_info"]["name"] == "local"
    assert body["evidence"] == started["evidence"]
    assert any("switched to local" in w for w in body["warnings"])


def test_provider_switch_to_cloud_with_confirmation() -> None:
    started = _investigate("The demo worker is down.")
    inv_id = started["investigation_id"]
    body = client.post(
        f"/api/investigations/{inv_id}/provider",
        json={"provider": "meta", "confirm_cloud": True},
    ).json()
    assert body["provider_info"]["name"] == "meta"
    # No key in tests: the next round falls back to simulated, honestly labeled.
    again = _turn(inv_id, "Any change?", kind="question")
    assert again["analysis_mode"] == "simulated"
    assert any("fell back to simulated" in w for w in again["warnings"])


def test_target_switch_warns_and_downgrades_plan() -> None:
    started = _investigate("The demo worker is down.")
    inv_id = started["investigation_id"]
    assert started["target"] == "local"
    body = client.post(
        f"/api/investigations/{inv_id}/target", json={"target": "remote"}
    ).json()
    assert body["target"] == "remote"
    assert any("wrong computer" in w for w in body["warnings"])
    open_steps = [s for s in body["plan"]["steps"] if s["status"] in ("suggested", "current")]
    assert open_steps
    assert all(s["kind"] != "AUTOMATED_READ_ONLY" for s in open_steps)
    # A follow-up round collects no further host measurements.
    calls_before = body["tool_calls_used"]
    again = _turn(inv_id, "The other machine shows the same symptom.", kind="observation")
    assert again["tool_calls_used"] == calls_before


def test_turn_screenshot_requires_consent_and_stays_metadata_only() -> None:
    from app.investigations import persistence

    started = _investigate("Excel will not open files from Teams.", target="remote")
    inv_id = started["investigation_id"]
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    denied = client.post(
        f"/api/investigations/{inv_id}/turn",
        data={"kind": "observation", "text": "See attached."},
        files={"screenshot": ("shot.png", png, "image/png")},
    )
    assert denied.status_code == 400
    body = client.post(
        f"/api/investigations/{inv_id}/turn",
        data={"kind": "observation", "text": "See attached.", "share_consent": "true"},
        files={"screenshot": ("shot.png", png, "image/png")},
    ).json()
    shots = [item for item in body["evidence"] if item["category"] == "screenshot"]
    assert len(shots) == 1
    assert shots[0]["data"]["bytes"] == len(png)
    assert "base64" not in json.dumps(shots[0]["data"])
    # Stored history keeps text only; image bytes never reach the database.
    reloaded = persistence.load_state(inv_id)
    assert reloaded is not None
    for message in reloaded.messages:
        assert "base64" not in json.dumps(message)


def test_assist_layer_survives_reload() -> None:
    from app.investigations import persistence

    started = _investigate("The demo worker is down.", provider="simulated")
    inv_id = started["investigation_id"]
    first_hyp = started["hypotheses"][0]["hypothesis_id"]
    client.post(
        f"/api/investigations/{inv_id}/hypotheses/{first_hyp}/status",
        json={"status": "weakened", "reason": "Looks stale."},
    )
    current_id = started["plan"]["current_step_id"]
    client.post(
        f"/api/investigations/{inv_id}/plan/steps/{current_id}/complete",
        json={"outcome": "Checked; still failing."},
    )
    reloaded = persistence.load_state(inv_id)
    assert reloaded is not None
    assert reloaded.provider_override == "simulated"
    assert reloaded.rounds_used == 1
    hyp = next(h for h in reloaded.hypotheses if h.hypothesis_id == first_hyp)
    assert hyp.status == "weakened"
    assert hyp.history[-1].reason.startswith("Technician judgment")
    assert reloaded.plan is not None
    done = next(s for s in reloaded.plan.steps if s.step_id == current_id)
    assert done.status == "done" and done.outcome == "Checked; still failing."
    assert reloaded.questions, "questions persist across restarts"


def test_v5_database_migrates_to_v6_with_defaults() -> None:
    from app.investigations import persistence

    started = _investigate("The demo worker is down.")
    inv_id = started["investigation_id"]
    conn = sqlite3.connect(persistence.db_path())
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == persistence.DB_VERSION
        conn.execute("DROP TABLE assist")
        conn.execute("PRAGMA user_version = 5")
        conn.commit()
    finally:
        conn.close()
    body = client.get(f"/api/investigations/{inv_id}").json()
    assert body["target"] == "local"
    assert body["hypotheses"], "assist layer rebuilds from the stored assessment"
    assert body["plan"] is not None
    conn = sqlite3.connect(persistence.db_path())
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == persistence.DB_VERSION
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# M019 progress / stagnation monitor
# ---------------------------------------------------------------------------


def _stall_state() -> InvestigationState:
    """A round whose model output repeats only already-tracked direction."""
    from app.schemas import ClarifyingQuestion, TroubleshootPlan, TroubleshootStep

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(question_id="q-1", question="When did it start?", why="timing")
    )
    state.plan = TroubleshootPlan(
        plan_id="tplan-x",
        updated_round=1,
        steps=[
            TroubleshootStep(step_id="step-1", instruction="Check the thing.", status="current")
        ],
        current_step_id="step-1",
    )
    state.assessment = validate_assessment_output(
        _final_json(
            [],
            questions=[{"question": "When did it start?", "why": "timing matters"}],
            plan={"steps": [{"instruction": "Check the thing.", "kind": "TECHNICIAN_CHECK"}]},
        ),
        set(),
        "m",
        "live",
    )
    return state


def test_repeated_question_is_withheld_and_visible() -> None:
    from app.analysis.assist import refresh_assist

    state = _stall_state()
    refresh_assist(state, 2, fresh_round=True)
    assert [q.question_id for q in state.questions] == ["q-1"], "no duplicate asked"
    assert any(r.title == "Repeated question withheld" for r in state.activity)
    assert any(r.title == "No new direction" for r in state.activity)
    assert not any("stalled" in w for w in state.warnings), "first stall stays quiet"


def test_consecutive_stalls_warn_with_alternatives() -> None:
    from app.analysis.assist import refresh_assist

    state = _stall_state()
    refresh_assist(state, 2, fresh_round=True)
    refresh_assist(state, 3, fresh_round=True)
    assert any("stalled" in w for w in state.warnings)
    warning = next(w for w in state.warnings if "stalled" in w)
    assert "re-verify" in warning
    assert any(r.title == "Investigation stalled" for r in state.activity)


def test_near_verbatim_paraphrase_is_withheld() -> None:
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1",
            question="Ask the technician to verify if the license server is running on the server side",
            why="scope", status="open", asked_round=1, source="model",
        )
    )
    state.assist_counters["q"] = 1
    state.assessment = validate_assessment_output(
        _final_json(
            [],
            questions=[{
                "question": "Ask the technician to confirm if the license server is running on the server side",
                "why": "scope",
            }],
        ),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 2, fresh_round=True)
    assert [q.question_id for q in state.questions] == ["q-1"]
    assert any(r.title == "Repeated question withheld" for r in state.activity)


def test_close_but_distinct_scoping_questions_survive() -> None:
    from app.analysis.assist import _near_verbatim

    assert not _near_verbatim(
        "Does it fail for local files too?",
        "Does it fail for Teams files too?",
    )
    assert _near_verbatim(
        "Ask the technician to verify if the license server is running",
        "Ask the technician to confirm if the license server is running",
    )


def test_withheld_repeat_visible_despite_progress() -> None:
    """A repeat stays in the record even when the round moves forward."""
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1", question="When did it start?", why="timing",
            status="open", asked_round=1, source="model",
        )
    )
    state.assist_counters["q"] = 1
    state.assessment = validate_assessment_output(
        _final_json(
            [],
            questions=[
                {"question": "When did it start?", "why": "repeat"},
                {"question": "Does it fail for others?", "why": "scope"},
            ],
        ),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 2, fresh_round=True)
    assert state.assist_counters.get("stall_rounds") == 0, "new question = progress"
    assert any(r.title == "Repeated question withheld" for r in state.activity)


def test_hyp_churn_with_repeats_still_counts_as_stall() -> None:
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion, TroubleshootPlan, TroubleshootStep

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1", question="When did it start?", why="timing",
            status="open", asked_round=1, source="model",
        )
    )
    state.assist_counters["q"] = 1
    state.plan = TroubleshootPlan(
        plan_id="tplan-x",
        updated_round=1,
        steps=[TroubleshootStep(step_id="step-1", instruction="Check the thing.", status="current")],
        current_step_id="step-1",
    )
    state.assessment = validate_assessment_output(
        _final_json(
            [],
            questions=[{"question": "When did it start?", "why": "timing"}],
            hypotheses=[{"title": "Brand new wording", "status": "active"}],
            plan={"steps": [{"instruction": "Check the thing.", "kind": "TECHNICIAN_CHECK"}]},
        ),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 2, fresh_round=True)
    assert state.assist_counters.get("stall_rounds") == 1
    assert any(r.title == "Revisited settled ground" for r in state.activity)


def test_progress_resets_stall_counter() -> None:
    from app.analysis.assist import refresh_assist

    state = _stall_state()
    refresh_assist(state, 2, fresh_round=True)
    assert state.assist_counters.get("stall_rounds") == 1
    state.assessment = validate_assessment_output(
        _final_json([], questions=[{"question": "Does it fail for others?", "why": "scope"}]),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 3, fresh_round=True)
    assert state.assist_counters.get("stall_rounds") == 0
    assert not any("stalled" in w for w in state.warnings)


def test_thin_answer_detector_is_narrow() -> None:
    from app.analysis.assist import _looks_uninformative

    assert _looks_uninformative("I don't have that information.")
    assert _looks_uninformative("Not sure.")
    assert _looks_uninformative("No idea.")
    assert not _looks_uninformative("I cannot reach that machine.")
    assert not _looks_uninformative("I can't do that test; no admin rights.")
    assert not _looks_uninformative("Not sure of the code, but the dialog mentioned Teams.")
    assert not _looks_uninformative("")
    assert not _looks_uninformative("I don't know. " + "But here's a photo. " * 10)


def test_thin_answer_streak_counts_and_resets() -> None:
    from app.analysis.assist import note_technician_answer

    state = _live_state(target="local")
    assert note_technician_answer(state, "No idea.") == 1
    assert note_technician_answer(state, "I don't have that information.") == 2
    assert note_technician_answer(state, "The error is 0x80070005.") == 0
    assert note_technician_answer(state, "Not sure.") == 1


def test_thin_streak_stalls_despite_new_questions() -> None:
    from app.analysis.assist import refresh_assist

    state = _live_state(target="local")
    state.assist_counters["thin_answers"] = 3
    state.assessment = validate_assessment_output(
        _final_json([], questions=[{"question": "One more question?", "why": "why"}]),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 4, fresh_round=True)
    assert state.assist_counters.get("stall_rounds") == 1
    assert any(r.title == "Answers giving no information" for r in state.activity)


def test_recovery_refresh_never_trips_stall_monitor() -> None:
    from app.analysis.assist import refresh_assist

    state = _stall_state()
    refresh_assist(state, 1)  # load recovery / re-check path: fresh_round=False
    refresh_assist(state, 1)
    assert "stall_rounds" not in state.assist_counters
    assert not any(r.title in ("No new direction", "Investigation stalled") for r in state.activity)


# ---------------------------------------------------------------------------
# M019 question lifecycle
# ---------------------------------------------------------------------------


def test_refined_question_supersedes_older() -> None:
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1", question="When did it start?", why="timing",
            status="open", asked_round=1, source="model",
        )
    )
    state.assist_counters["q"] = 1
    state.assessment = validate_assessment_output(
        _final_json(
            [],
            questions=[{
                "question": "When did it start, and what changed that morning?",
                "why": "timing plus trigger",
            }],
        ),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 2, fresh_round=True)
    old = next(q for q in state.questions if q.question_id == "q-1")
    assert old.status == "superseded"
    assert "q-2" in old.retired_note
    assert old.question == "When did it start?", "history preserved"
    assert any(r.title == "Question lifecycle" for r in state.activity)


def test_fallback_question_retires_when_model_question_arrives() -> None:
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1",
            question="Can you provide or check the following: exact error text",
            why="fallback", status="open", asked_round=1, source="fallback",
        )
    )
    state.assist_counters["q"] = 1
    state.assessment = validate_assessment_output(
        _final_json(
            [], questions=[{"question": "What is the exact error on screen?", "why": "scope"}]
        ),
        set(),
        "m",
        "live",
    )
    refresh_assist(state, 2, fresh_round=True)
    old = next(q for q in state.questions if q.question_id == "q-1")
    assert old.status == "retired"
    assert "took priority" in old.retired_note
    assert len(state.questions) == 2, "retired questions stay in history"


def test_target_question_retires_once_target_known() -> None:
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="remote")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1",
            question="Is the affected computer this one?",
            why="scope", status="open", asked_round=1, source="target",
        )
    )
    state.assessment = validate_assessment_output(_final_json([]), set(), "m", "live")
    refresh_assist(state, 2, fresh_round=True)
    old = next(q for q in state.questions if q.question_id == "q-1")
    assert old.status == "retired"
    assert "target" in old.retired_note.lower()


def test_stale_open_question_ages_out() -> None:
    from app.analysis.assist import refresh_assist
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1", question="Does it fail for others?", why="scope",
            status="open", asked_round=1, source="model",
        )
    )
    state.assessment = validate_assessment_output(_final_json([]), set(), "m", "live")
    refresh_assist(state, 6, fresh_round=True)
    old = next(q for q in state.questions if q.question_id == "q-1")
    assert old.status == "retired"
    assert "history" in old.retired_note


def test_unable_turn_blocks_question() -> None:
    started = _investigate("Something is broken.", target="unknown")
    inv_id = started["investigation_id"]
    first_id = started["questions"][0]["question_id"]
    body = _turn(inv_id, "I cannot reach that machine.", kind="unable", question_id=first_id)
    blocked = next(q for q in body["questions"] if q["question_id"] == first_id)
    assert blocked["status"] == "blocked"
    assert blocked["answer"] == "I cannot reach that machine."
    assert (
        client.post(
            f"/api/investigations/{inv_id}/turn",
            data={"kind": "answer", "text": "late", "question_id": first_id},
        ).status_code
        == 409
    )


def test_legacy_question_validates_with_lifecycle_defaults() -> None:
    from app.schemas import ClarifyingQuestion

    legacy = ClarifyingQuestion.model_validate({"question_id": "q-0", "question": "Q?"})
    assert legacy.status == "open"
    assert legacy.asked_round == 0
    assert legacy.source == "model"
    assert legacy.retired_note == ""


def test_plan_step_duping_open_question_is_skipped() -> None:
    """M019: a check restating an open question adds no direction."""
    from app.schemas import ClarifyingQuestion

    state = _live_state(target="local")
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1",
            question="Is Contoso Planner slow for all users or just one?",
            why="scope", status="open", asked_round=1, source="model",
        )
    )
    state.assist_counters["q"] = 1
    state.assessment = validate_assessment_output(
        _final_json(
            [],
            plan={
                "steps": [
                    {
                        "instruction": "Check if Contoso Planner is slow for all users on the laptop or just the user",
                        "kind": "TECHNICIAN_CHECK",
                    },
                    {
                        "instruction": "Check how much RAM is free while Planner is slow.",
                        "kind": "TECHNICIAN_CHECK",
                    },
                ]
            },
        ),
        set(),
        "m",
        "live",
    )
    merge_plan(state, 2)
    assert state.plan is not None
    instructions = [s.instruction for s in state.plan.steps]
    assert len(instructions) == 1, f"dupe step must be skipped, kept: {instructions}"
    assert "RAM" in instructions[0]
