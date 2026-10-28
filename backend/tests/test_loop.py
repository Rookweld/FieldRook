"""Reasoning loop protocol: every tool call gets an answer, budgets hold."""

import asyncio
import json

from app.analysis.loop import _run_live
from app.analysis.provider import ProviderCapabilities
from app.config import Settings
from app.investigations.store import InvestigationState


def _settings() -> Settings:
    return Settings(
        model_api_key="test-key-not-real",
        model_base_url="https://api.meta.ai/v1",
        model_name="test-model",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )


def _final_json() -> str:
    return json.dumps(
        {
            "summary": "Test summary.",
            "facts": [{"statement": "OS info collected.", "evidence_ids": ["ev-1"]}],
            "causes": [],
            "uncertainties": [],
            "missing_evidence": [],
            "next_actions": [],
            "explanation": "Test explanation.",
        }
    )


class _ScriptedProvider:
    """Replays scripted assistant messages, verifying protocol invariants."""

    def __init__(self, script: list[dict]) -> None:
        self._script = script
        self.turns = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            text=True, vision=True, tool_calling=True,
            structured_output=True, processing_location="cloud",
        )

    def model_label(self) -> str:
        return "test-model"

    async def chat(self, messages, tools=None, json_only=False, cancel_scope=None):  # noqa: ANN001, ANN002, ANN003, ANN004
        called: set[str] = set()
        for message in messages:
            for tool_call in message.get("tool_calls") or []:
                if tool_call.get("id"):
                    called.add(tool_call["id"])
        answered = {
            message.get("tool_call_id")
            for message in messages
            if message.get("role") == "tool"
        }
        missing = called - answered
        assert not missing, f"unanswered tool calls: {missing}"
        reply = self._script[min(self.turns, len(self._script) - 1)]
        self.turns += 1
        return reply


def _state() -> InvestigationState:
    return InvestigationState(
        id="inv-test",
        problem="Test problem.",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "Test problem."}],
    )


def test_budget_cutoff_still_answers_every_call() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                    {"id": "c2", "type": "function", "function": {"name": "get_dns_config", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _final_json(), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=1))  # type: ignore[arg-type]
    assert state.tool_calls_made == 1
    assert state.assessment is not None
    assert state.assessment.mode == "live"
    tool_messages = [m for m in state.messages if m.get("role") == "tool"]
    assert {m["tool_call_id"] for m in tool_messages} == {"c1", "c2"}


def test_unknown_tool_rejected_without_execution() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "format_drive", "arguments": "{}"}},
                    {"id": "c2", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _final_json(), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))  # type: ignore[arg-type]
    assert state.tool_calls_made == 1
    kinds = [record.kind for record in state.activity]
    assert "error" in kinds
    assert state.assessment is not None


def _assessment_json(evidence_ids: list[str]) -> str:
    return json.dumps(
        {
            "summary": "Test summary.",
            "facts": [{"statement": "OS info collected.", "evidence_ids": evidence_ids}],
            "causes": [],
            "uncertainties": [],
            "missing_evidence": [],
            "next_actions": [],
            "explanation": "Test explanation.",
        }
    )


def test_citation_repair_round_demands_evidence_refs() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _assessment_json([]), "tool_calls": []},
            {"role": "assistant", "content": _assessment_json(["ev-1"]), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))  # type: ignore[arg-type]
    assert provider.turns == 3
    assert state.assessment is not None
    assert state.assessment.facts[0].evidence_ids == ["ev-1"]
    titles = [record.title for record in state.activity]
    assert "Requesting evidence citations" in titles


def test_same_round_duplicate_call_answered_once() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                    {"id": "c2", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                    {"id": "c3", "type": "function", "function": {"name": "get_dns_config", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _assessment_json(["ev-1"]), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))  # type: ignore[arg-type]
    assert state.tool_calls_made == 2
    tool_messages = {m["tool_call_id"]: json.loads(m["content"]) for m in state.messages if m.get("role") == "tool"}
    assert set(tool_messages) == {"c1", "c2", "c3"}
    assert tool_messages["c2"]["duplicate_of"] == "ev-1"
    titles = [record.title for record in state.activity]
    assert "Duplicate get_os_info skipped" in titles


def test_duplicate_scope_resets_each_round() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c2", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _assessment_json(["ev-2"]), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))  # type: ignore[arg-type]
    assert state.tool_calls_made == 2
    tool_messages = {m["tool_call_id"]: json.loads(m["content"]) for m in state.messages if m.get("role") == "tool"}
    assert "duplicate_of" not in tool_messages["c2"]


def test_tool_messages_carry_evidence_ids() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _assessment_json(["ev-1"]), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))  # type: ignore[arg-type]
    tool_messages = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert json.loads(tool_messages[0]["content"])["evidence_id"] == "ev-1"
