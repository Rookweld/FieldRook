"""M007 investigation intelligence: contradictions, rechecks, loop discipline."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.analysis.loop import _run_live
from app.analysis.provider import ProviderCapabilities
from app.config import Settings
from app.investigations.store import InvestigationState
from app.main import app

client = TestClient(app)


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200
    return response.json()


def test_network_report_contradiction_surfaced() -> None:
    body = _investigate("The network is down on this machine, I am sure the cable is unplugged.")
    assert body["contradictions"], "adapters-Up vs network-down report must be flagged"
    hit = body["contradictions"][0]
    assert hit["evidence_ids"]
    known = {item["id"] for item in body["evidence"]}
    assert set(hit["evidence_ids"]) <= known
    assert "down" in hit["description"].lower()
    assert any(
        "contradiction" in uncertainty.lower()
        for uncertainty in body["assessment"]["uncertainties"]
    )


def test_service_process_contradiction_surfaced() -> None:
    body = _investigate(
        "Is the Windows Update service healthy?", service_name="wuauserv"
    )
    # Fixture wuauserv: service Stopped, hosted process found (known mirror gap,
    # now surfaced deterministically instead of papered over).
    assert any(
        "Stopped" in hit["description"] and "process" in hit["description"].lower()
        for hit in body["contradictions"]
    )


def test_consistent_dns_evidence_has_no_contradiction() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    assert body["contradictions"] == []


def test_contradiction_drives_targeted_recheck() -> None:
    body = _investigate("The network is down on this machine, I am sure the cable is unplugged.")
    assert body["suggested_rechecks"], "a contradiction should recommend a re-check"
    suggestion = body["suggested_rechecks"][0]
    assert suggestion["tool_name"] == "get_network_adapters"
    assert suggestion["evidence_id"] in {
        item["id"] for item in body["evidence"] if item["category"] == "net_adapters"
    }
    assert "disagrees" in suggestion["reason"]


def test_stale_evidence_suggests_recheck(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FIELDROOK_EVIDENCE_TTL_S", "-1")  # everything is stale
    body = _investigate("DNS does not resolve anything since this morning.")
    assert body["suggested_rechecks"]
    assert all(
        suggestion["tool_name"] for suggestion in body["suggested_rechecks"]
    )
    assert "TTL" in body["suggested_rechecks"][0]["reason"]


def test_fresh_consistent_evidence_suggests_no_recheck() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    assert body["suggested_rechecks"] == []
    assert body["tool_calls_used"] == 2
    assert body["tool_calls_max"] == 12


def test_suggested_recheck_points_at_rerunnable_evidence() -> None:
    from app.investigations import persistence

    state = InvestigationState(
        id="inv-stale-test", problem="Stale probe.", service_name=None, has_image=False
    )
    old = state.add_evidence(
        category="dns_config",
        source="tool:get_dns_config:fixture",
        data={"summary": "x", "warnings": [], "count": 1},
        tool_name="get_dns_config",
        tool_args={},
    )
    old.collected_at = datetime.now(timezone.utc) - timedelta(hours=2)
    state.add_evidence(category="screenshot", source="upload:screenshot", data={})
    persistence.save_state(state)
    fetched = client.get("/api/investigations/inv-stale-test").json()
    assert [s["evidence_id"] for s in fetched["suggested_rechecks"]] == [old.id]


def _settings() -> Settings:
    return Settings(
        model_api_key="test-key-not-real",
        model_base_url="https://api.meta.ai/v1",
        model_name="test-model",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )


def _final_json(evidence_ids: list[str]) -> str:
    return json.dumps(
        {
            "summary": "Test summary.",
            "facts": [{"statement": "OS info collected.", "evidence_ids": evidence_ids}],
            "causes": [],
            "uncertainties": ["Still unknown."],
            "missing_evidence": [],
            "next_actions": [],
            "explanation": "Test explanation.",
        }
    )


class _ScriptedProvider:
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

    async def chat(self, messages, tools=None, json_only=False):  # noqa: ANN001, ANN002, ANN003
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


def test_cross_round_recheck_is_linked_and_compared() -> None:
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
                "content": "re-checking get_os_info for a state change since ev-1",
                "tool_calls": [
                    {"id": "c2", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _final_json(["ev-2"]), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=4))  # type: ignore[arg-type]
    assert state.tool_calls_made == 2
    assert len(state.refreshes) == 1
    assert state.refreshes[0].old_evidence_id == "ev-1"
    assert state.refreshes[0].new_evidence_id == "ev-2"
    assert state.refreshes[0].verdict == "unchanged"
    assert state.evidence[1].refresh_of == "ev-1"
    assert any(record.kind == "reverify" for record in state.activity)


def test_loop_stops_after_unproductive_rounds() -> None:
    provider = _ScriptedProvider(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                    {"id": "c2", "type": "function", "function": {"name": "get_os_info", "arguments": "{}"}},
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c3", "type": "function", "function": {"name": "format_drive", "arguments": "{}"}},
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c4", "type": "function", "function": {"name": "format_drive", "arguments": "{}"}},
                ],
            },
            {"role": "assistant", "content": _final_json(["ev-1"]), "tool_calls": []},
        ]
    )
    state = _state()
    asyncio.run(_run_live(state, provider, _settings(), True, max_new_calls=8))  # type: ignore[arg-type]
    titles = [record.title for record in state.activity]
    assert "Stopping early: no new evidence" in titles
    assert provider.turns == 4  # 3 tool rounds + final assessment (4th round skipped)
    assert state.assessment is not None
