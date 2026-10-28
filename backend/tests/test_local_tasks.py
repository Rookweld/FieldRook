"""M017 lightweight local intelligence: profiles, task pipeline, cancel."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.analysis.local_profiles import (
    describe_profile,
    effective_vision,
    resolve_profile,
    vision_mismatch,
)
from app.analysis.local_tasks import (
    assemble_assessment,
    evidence_digest,
    extract_json,
    missing_keys,
    plan_prompt,
    reassess_prompt,
    triage_prompt,
)
from app.analysis.loop import _run_local_tasks
from app.analysis.provider import (
    LocalEndpointProvider,
    _to_ollama_messages,
    cached_server_caps,
    probe_ollama,
)
from app.analysis.validate import ModelAnalysisError
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


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


def test_resolve_profile_curated_and_default() -> None:
    known = resolve_profile("qwen3:4b")
    assert known.source == "curated"
    assert known.context_window == 262144
    assert known.thinking is True
    unknown = resolve_profile("mystery-model:99b")
    assert unknown.source == "default"
    assert unknown.vision is False
    assert unknown.perf_class == "unknown"
    assert describe_profile(unknown)["model"] == "mystery-model:99b"


def test_effective_vision_needs_flag_and_evidence() -> None:
    vl = resolve_profile("qwen3-vl:8b")
    text = resolve_profile("qwen3:4b")
    assert effective_vision(False, vl, ["vision"]) is False
    assert effective_vision(True, vl, []) is True
    assert effective_vision(True, text, []) is False
    assert effective_vision(True, text, ["completion", "vision"]) is True
    assert vision_mismatch(True, text, []) is not None
    assert vision_mismatch(True, vl, []) is None
    assert vision_mismatch(False, text, []) is None


def test_ollama_probe_never_raises_and_rejects_garbage() -> None:
    assert probe_ollama("http://127.0.0.1:9") is False
    assert cached_server_caps("not-a-url", "x") == []
    assert cached_server_caps("http://127.0.0.1:9/v1", "x") == []


# ---------------------------------------------------------------------------
# Task prompts + JSON handling
# ---------------------------------------------------------------------------


def test_task_prompts_are_compact_and_scoped() -> None:
    triage = triage_prompt("Excel fails.", "ev-1: service via x", "remote")
    assert len(triage) < 1500
    assert "different computer" in triage
    local = triage_prompt("Excel fails.", "", "local")
    assert "different computer" not in local
    plan = plan_prompt("p", "ctx", "remote")
    assert "TECHNICIAN_CHECK" in plan
    assert "AUTOMATED_READ_ONLY" not in plan
    reassess = reassess_prompt(["H1"], "obs")
    assert "H1" in reassess and "obs" in reassess
    assert "do not repeat" not in reassess.lower()
    repeated = reassess_prompt(["H1"], "obs", ["Is it plugged in?"])
    assert "Is it plugged in?" in repeated
    assert "do not repeat" in repeated.lower()
    assert "more details" in triage_prompt("p", "", "local")


def test_extract_json_finds_balanced_span() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure! {"a": {"b": [1, 2]}} thanks') == {"a": {"b": [1, 2]}}
    assert extract_json('{"a": "brace } inside"}') == {"a": "brace } inside"}
    assert extract_json("no json here") is None
    assert extract_json('{"a": }') is None
    assert extract_json("[1, 2]") is None


def test_missing_keys_reports_gaps() -> None:
    assert missing_keys({"question": "q"}, "triage") == ["why", "hypotheses", "next_check", "unknowns"]
    assert missing_keys({"steps": []}, "plan") == []


def test_evidence_digest_is_compact() -> None:
    items = [
        {"id": f"ev-{i}", "category": "c", "tool_name": "t", "source": "tool:t:x", "data": {"a": 1}}
        for i in range(20)
    ]
    digest = evidence_digest(items)
    assert "ev-1" in digest and "(+8 more)" in digest


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _triage() -> dict:
    return {
        "question": "Does it fail for local files too?",
        "why": "Separates app faults from file-access faults.",
        "hypotheses": [{"title": "Teams file-access problem", "why": "Local files work."}],
        "next_check": "Open the file from local disk.",
        "unknowns": ["Exact error text."],
    }


def _plan() -> dict:
    return {
        "steps": [
            {
                "instruction": "Open the file from local disk.",
                "why": "Separates app faults from access faults.",
                "kind": "TECHNICIAN_CHECK",
                "expect": "Works locally: access path fault.",
            }
        ]
    }


def test_assemble_maps_model_parts() -> None:
    result, warnings, parts = assemble_assessment(
        "Excel fails.", [], _triage(), _plan(), None, "local/qwen3:4b", "remote"
    )
    assert parts == ["triage", "plan"]
    assert warnings == []
    assert result.mode == "live"
    assert result.model == "local/qwen3:4b"
    assert result.provider == "local"
    assert result.causes[0].title == "Teams file-access problem"
    assert result.causes[0].likelihood == "low"
    assert result.suggested_questions[0].question.startswith("Does it fail")
    assert result.suggested_plan is not None
    assert result.suggested_plan.steps[0].kind == "TECHNICIAN_CHECK"
    assert result.next_steps[0].impact == "read-only"


def test_assemble_reassess_weakens_and_questions() -> None:
    reassess = {"verdict": "App-wide failure less likely.", "weakened": ["Damaged install"], "next_step": "Does Teams web open it?"}
    result, warnings, parts = assemble_assessment(
        "Excel fails.", [], None, _plan(), reassess, "local/m", "local"
    )
    assert parts == ["reassess", "plan"]
    assert result.causes == [], "follow-ups keep tracked hypotheses; no junk causes"
    assert result.suggested_hypotheses[0].status == "weakened"
    assert result.suggested_questions[0].question == "Does Teams web open it?"


def test_assemble_reassess_ask_prefixed_next_step_becomes_question() -> None:
    """M019: 'Ask the technician to ...' is a question, not a check."""
    reassess = {
        "verdict": "Need the exact text.",
        "weakened": [],
        "next_step": "Ask the technician to provide the exact error message.",
    }
    result, _warnings, parts = assemble_assessment(
        "Excel fails.", [], None, None, reassess, "local/m", "local", plan_skipped=True
    )
    assert parts == ["reassess"]
    assert result.suggested_plan is None
    assert len(result.suggested_questions) == 1
    assert result.suggested_questions[0].question.startswith("Ask the technician")


def test_reassess_prompt_prefers_discriminating_questions_after_surprises() -> None:
    prompt = reassess_prompt(["H1"], "Something unexpected.", [])
    assert "discriminate" in prompt
    assert "contradicts" in prompt
    assert "ruled out" in prompt
    assert "gave no usable information" not in prompt
    assert "gave no usable information" in reassess_prompt(["H1"], "X.", [], thin_streak=2)


def test_assemble_reassess_check_like_next_step_becomes_step() -> None:
    """M019: a check-like reassess next_step routes to a plan step, not a question."""
    reassess = {"verdict": "App-wide failure less likely.", "weakened": [], "next_step": "Check Teams permissions."}
    result, _warnings, parts = assemble_assessment(
        "Excel fails.", [], None, None, reassess, "local/m", "local", plan_skipped=True
    )
    assert parts == ["reassess"]
    assert result.suggested_questions == []
    assert result.suggested_plan is not None
    assert result.suggested_plan.steps[0].instruction == "Check Teams permissions."
    assert result.suggested_plan.steps[0].kind == "TECHNICIAN_CHECK"


def test_assemble_total_failure_is_labeled() -> None:
    result, warnings, parts = assemble_assessment("p", [], None, None, None, "local/m", "local")
    assert parts == []
    assert len(warnings) == 2
    assert "no usable output" in " ".join(warnings).lower()
    assert result.causes[0].likelihood == "low"
    assert "observations are missing" in result.causes[0].title


# ---------------------------------------------------------------------------
# Provider task path (mocked transport)
# ---------------------------------------------------------------------------


class _MockTransport:
    """Stands in for _ollama_chat / _chat_completions."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls = 0

    async def ollama(self, base, model, messages, json_only, num_predict, timeout=None, cancel_scope=None):  # noqa: ANN001, ANN002, ANN003
        self.calls += 1
        return {"role": "assistant", "content": self.replies.pop(0)}

    def payload_of(self, index: int = 0):  # placeholder, unused
        return None


def _local_provider() -> LocalEndpointProvider:
    return LocalEndpointProvider(
        _settings(
            local_model_url="http://127.0.0.1:11434/v1",
            local_model_name="qwen3:4b",
            local_api="ollama",
        )
    )


def test_run_task_parses_and_warns_on_gaps(monkeypatch) -> None:
    provider = _local_provider()
    transport = _MockTransport(['{"question": "Q?"}'])
    monkeypatch.setattr(provider, "_ollama_chat", transport.ollama)
    parsed, warnings = asyncio.run(provider.run_task("triage", "prompt"))
    assert parsed == {"question": "Q?"}
    assert any("missing keys" in w for w in warnings)
    assert transport.calls == 1


def test_run_task_repairs_once_then_gives_up(monkeypatch) -> None:
    provider = _local_provider()
    transport = _MockTransport(["not json at all", '{"steps": []}'])
    monkeypatch.setattr(provider, "_ollama_chat", transport.ollama)
    parsed, warnings = asyncio.run(provider.run_task("plan", "prompt"))
    assert parsed == {"steps": []}
    assert any("repair retry" in w for w in warnings)
    assert transport.calls == 2


def test_run_task_failure_returns_none(monkeypatch) -> None:
    provider = _local_provider()

    async def boom(*args, **kwargs):  # noqa: ANN001, ANN002
        raise ModelAnalysisError("timeout")

    monkeypatch.setattr(provider, "_ollama_chat", boom)
    parsed, warnings = asyncio.run(provider.run_task("triage", "prompt"))
    assert parsed is None
    assert any("deterministic fallback" in w for w in warnings)


def test_chat_rejects_tools_for_local() -> None:
    provider = _local_provider()
    with pytest.raises(ModelAnalysisError, match="tool-calling"):
        asyncio.run(provider.chat([{"role": "user", "content": "hi"}], tools=[{"type": "function"}]))


def test_think_defaults_off() -> None:
    assert _local_provider().think_enabled() is False
    forced = LocalEndpointProvider(_settings(local_think="on"))
    assert forced.think_enabled() is True


def test_ollama_message_conversion() -> None:
    converted = _to_ollama_messages(
        [
            {"role": "user", "content": "hi"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "see"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
                ],
            },
        ]
    )
    assert converted[0] == {"role": "user", "content": "hi"}
    assert converted[1]["images"] == ["QUJD"]
    assert converted[1]["content"] == "see"


# ---------------------------------------------------------------------------
# Pipeline + cancel (mocked tasks)
# ---------------------------------------------------------------------------


def _pipeline_state(**overrides) -> InvestigationState:
    params: dict = {
        "id": "inv-local-test",
        "problem": "Excel fails.",
        "service_name": None,
        "has_image": False,
        "messages": [{"role": "user", "content": "Excel fails."}],
    }
    params.update(overrides)
    return InvestigationState(**params)


class _TaskProvider:
    name = "local"

    def __init__(self, parts: dict) -> None:
        self._parts = parts
        self.calls: list[str] = []
        self.last_stats = {"wall_s": 1.2, "eval_count": 50, "eval_duration_s": 1.0}

    def capabilities(self):
        from app.analysis.provider import ProviderCapabilities

        return ProviderCapabilities(
            text=True, vision=False, tool_calling=False,
            structured_output=False, processing_location="local",
        )

    def model_label(self) -> str:
        return "local/mocked"

    async def run_task(self, task, prompt, timeout_s=None, images=None, cancel_scope=None):  # noqa: ANN001, ANN002, ANN003
        self.calls.append(task)
        return self._parts.get(task), []


def test_pipeline_assembles_live_assessment() -> None:
    state = _pipeline_state()
    provider = _TaskProvider({"triage": _triage(), "plan": _plan()})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False))
    assert provider.calls == ["triage"], "M019: plan skipped when triage decides"
    assert state.assessment is not None
    assert state.assessment.mode == "live"
    assert state.assessment.model == "local/mocked"
    assert state.assessment.suggested_questions
    assert any(r.title == "Single-decision round" for r in state.activity)
    assert any(r.title == "Local inference stats" for r in state.activity)
    assert state.assessment.suggested_plan is not None
    assert state.assessment.suggested_plan.steps[0].instruction == "Open the file from local disk."


def test_pipeline_followup_reassesses() -> None:
    from app.schemas import Hypothesis

    state = _pipeline_state()
    state.hypotheses.append(Hypothesis(hypothesis_id="hyp-1", title="Damaged install"))
    state.messages.append({"role": "user", "content": "Technician observation: local files open."})
    provider = _TaskProvider(
        {
            "reassess": {"verdict": "Less likely.", "weakened": ["Damaged install"], "next_step": "Check Teams."},
            "plan": _plan(),
        }
    )
    asyncio.run(_run_local_tasks(state, provider, _settings(), True))
    assert provider.calls == ["reassess"], "M019: plan skipped when reassess decides"
    assert state.assessment is not None
    assert state.assessment.suggested_hypotheses[0].status == "weakened"
    assert state.assessment.suggested_plan is not None, "check-like next step becomes a step"
    assert state.assessment.suggested_plan.steps[0].instruction == "Check Teams."


def test_local_path_collects_host_evidence_for_local_target() -> None:
    """M018: a local model on the local host must see host measurements."""
    state = _pipeline_state(target="local")
    provider = _TaskProvider({"triage": _triage(), "plan": _plan()})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False, True))
    assert state.tool_calls_made > 0
    host_items = [e for e in state.evidence if (e.source or "").startswith("tool:")]
    assert host_items, "local target must yield host-sourced evidence"
    assert provider.calls == ["triage"]
    assert state.assessment is not None


def test_local_path_collects_nothing_for_remote_target() -> None:
    """M018: remote targets still collect zero host evidence on local path."""
    state = _pipeline_state(target="remote")
    provider = _TaskProvider({"triage": _triage(), "plan": _plan()})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False, True))
    assert state.tool_calls_made == 0
    host_items = [e for e in state.evidence if (e.source or "").startswith("tool:")]
    assert not host_items
    assert provider.calls == ["triage"]


def test_pipeline_total_failure_substitutes() -> None:
    state = _pipeline_state()
    provider = _TaskProvider({})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False))
    assert provider.calls == ["triage", "plan"], "plan runs as recovery when starved"
    assert state.assessment is not None
    assert state.assessment.mode == "simulated"
    assert any("no usable output" in w for w in state.warnings)


def test_plan_skipped_when_direction_already_pending() -> None:
    """M019: a failed primary task does not trigger plan when work is pending."""
    from app.schemas import ClarifyingQuestion

    state = _pipeline_state()
    state.questions.append(
        ClarifyingQuestion(question_id="q-old", question="Does it fail for others?", why="Scope.")
    )
    provider = _TaskProvider({})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False))
    assert provider.calls == ["triage"], "existing open question stands; no recovery call"
    assert state.assessment is not None


def test_reassess_question_like_next_step_stays_a_question() -> None:
    """M019: next steps phrased as questions route to questions, not steps."""
    from app.schemas import Hypothesis

    state = _pipeline_state()
    state.hypotheses.append(Hypothesis(hypothesis_id="hyp-1", title="Damaged install"))
    state.messages.append({"role": "user", "content": "Technician observation: local files open."})
    provider = _TaskProvider(
        {"reassess": {"verdict": "Less likely.", "weakened": [], "next_step": "Does Teams web work?"}}
    )
    asyncio.run(_run_local_tasks(state, provider, _settings(), True))
    assert provider.calls == ["reassess"]
    assert state.assessment is not None
    assert any("Does Teams web work?" in q.question for q in state.assessment.suggested_questions)
    assert state.assessment.suggested_plan is None


def test_fallback_missing_evidence_is_technician_meaningful() -> None:
    """M018: fallback asks render as questions; internal notes must not leak."""
    from app.analysis.local_tasks import assemble_assessment

    result, _warnings, _parts = assemble_assessment(
        "Excel fails.", [], None, None, None, "local/mocked", "remote"
    )
    assert result.missing_evidence, "fallback must still ask something"
    surfaced = list(result.missing_evidence)
    surfaced.extend(c.title for c in result.causes)
    surfaced.extend(c.description for c in result.causes)
    for item in surfaced:
        lowered = item.lower()
        assert "triage did not answer" not in lowered
        assert "usable local-model" not in lowered
        assert "local model call failed" not in lowered
        assert "deterministic" not in lowered


def test_cancel_flag_honored_between_tasks() -> None:
    from app.investigations import persistence

    body = _investigate("Excel fails on the laptop.")
    inv_id = body["investigation_id"]
    assert body["rounds_used"] == 1
    persistence.request_cancel(inv_id, 1)
    assert persistence.cancel_requested(inv_id, 1) is True
    response = client.post(f"/api/investigations/{inv_id}/cancel")
    assert response.status_code == 200
    # A local round honors a same-round flag before any model call.
    state = _pipeline_state(id=inv_id, rounds_used=1)
    provider = _TaskProvider({"triage": _triage(), "plan": _plan()})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False))
    assert provider.calls == []
    assert state.assessment is None
    assert any("cancelled" in w.lower() for w in state.warnings)
    assert persistence.cancel_requested(inv_id, 1) is False, "honoring clears the flag"


def test_stale_cancel_flag_never_aborts_a_later_round() -> None:
    from app.investigations import persistence

    body = _investigate("Excel fails on the laptop.")
    inv_id = body["investigation_id"]
    # Flag set during round 1 but consumed by no model call (e.g. the round
    # ran on the simulated provider, which makes none).
    persistence.request_cancel(inv_id, 1)
    # A later local round must proceed and reap the stale flag.
    state = _pipeline_state(id=inv_id, rounds_used=2)
    provider = _TaskProvider({"triage": _triage(), "plan": _plan()})
    asyncio.run(_run_local_tasks(state, provider, _settings(), False))
    assert provider.calls == ["triage"]
    assert state.assessment is not None
    assert not any("cancelled" in w.lower() for w in state.warnings)
    assert persistence.cancel_requested(inv_id, 2) is False, "stale flag is reaped"


def test_connection_test_reports_unconfigured() -> None:
    body = client.post("/api/providers/local/test").json()
    assert body["ok"] is False
    assert body["profile"]["source"] in ("curated", "default")


def test_providers_local_entry_carries_profile() -> None:
    body = client.get("/api/providers").json()
    local = next(entry for entry in body if entry["name"] == "local")
    assert local["tool_calling"] is False
    assert local["profile"]["model"]
    assert local["api_style"] in ("openai", "ollama", "unresolved")
