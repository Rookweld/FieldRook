"""M022: knowledge + collector context actually reaches model turns."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis.local_tasks import reassess_prompt, triage_prompt
from app.analysis.loop import _run_local_tasks, reference_excerpts_for
from app.config import Settings
from app.investigations.store import InvestigationState, store
from app.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "collector" / "samples" / "sample_basic.zip"


def _user_texts(inv_id: str) -> list[str]:
    state = store.get(inv_id)
    assert state is not None
    return [
        str(m.get("content", ""))
        for m in state.messages
        if m.get("role") == "user" and isinstance(m.get("content"), str)
    ]


def _system_texts(inv_id: str) -> list[str]:
    state = store.get(inv_id)
    assert state is not None
    return [
        str(m.get("content", ""))
        for m in state.messages
        if m.get("role") == "system" and isinstance(m.get("content"), str)
    ]


def _new_investigation(problem: str) -> str:
    response = client.post("/api/investigations", data={"problem": problem})
    assert response.status_code == 200
    return response.json()["investigation_id"]


def _import_sample(inv_id: str) -> None:
    with SAMPLE.open("rb") as handle:
        response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("sample_basic.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert response.status_code == 200


def _followup(inv_id: str, message: str = "Any change after the import?") -> None:
    response = client.post(
        f"/api/investigations/{inv_id}/followup", json={"message": message}
    )
    assert response.status_code == 200


def test_initial_turn_carries_knowledge_block_user_only() -> None:
    inv_id = _new_investigation("DNS does not resolve on the field laptop")
    users = _user_texts(inv_id)
    assert any("Reference excerpts" in text for text in users)
    assert any("ref-dns-triage" in text for text in users)
    systems = _system_texts(inv_id)
    assert systems, "expected a system prompt"
    assert all("Reference excerpts" not in text for text in systems)
    assert all("DNS Triage for Workstations" not in text for text in systems)


def test_initial_turn_without_match_sends_no_block() -> None:
    inv_id = _new_investigation("Printer offline on field laptop")
    assert all("Reference excerpts" not in text for text in _user_texts(inv_id))


def test_collector_arrival_reinjects_knowledge_once() -> None:
    inv_id = _new_investigation("Printer offline on field laptop")
    assert all("Reference excerpts" not in text for text in _user_texts(inv_id))
    _import_sample(inv_id)
    _followup(inv_id)
    hits = [text for text in _user_texts(inv_id) if "Reference excerpts" in text]
    assert len(hits) == 1
    assert "Collector evidence" in hits[0] or any(
        "Collector evidence" in text for text in _user_texts(inv_id)
    )


def test_no_duplicate_knowledge_block_when_initial_matched() -> None:
    inv_id = _new_investigation("DNS does not resolve on the field laptop")
    _import_sample(inv_id)
    _followup(inv_id)
    hits = [text for text in _user_texts(inv_id) if "Reference excerpts" in text]
    assert len(hits) == 1


def test_reference_excerpts_fail_closed() -> None:
    assert reference_excerpts_for("") == []
    assert reference_excerpts_for("Printer offline on field laptop") == []
    assert len(reference_excerpts_for("DNS does not resolve on the field laptop")) >= 1


def test_prompt_defaults_unchanged_without_context() -> None:
    assert triage_prompt("p", "e", "local") == triage_prompt(
        "p", "e", "local", knowledge_context=None
    )
    assert reassess_prompt(["h"], "o") == reassess_prompt(
        ["h"], "o", knowledge_context=None
    )
    assert "Reference excerpts" not in triage_prompt("p", "e", "local")
    block = "Reference excerpts — quoted context:\n[1] x"
    assert block in triage_prompt("p", "e", "local", knowledge_context=block)
    assert block in reassess_prompt(["h"], "o", knowledge_context=block)


class _RecordingProvider:
    name = "local"
    last_stats = {"wall_s": 1.0, "eval_count": 10, "eval_duration_s": 0.5}

    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    def capabilities(self):  # noqa: ANN001 - stub mirrors test_local_tasks
        from app.analysis.provider import ProviderCapabilities

        return ProviderCapabilities(
            text=True, vision=False, tool_calling=False,
            structured_output=False, processing_location="local",
        )

    def model_label(self) -> str:
        return "local/recording"

    async def run_task(self, task, prompt, timeout_s=None, images=None, cancel_scope=None):  # noqa: ANN001, ANN002, ANN003
        self.prompts[task] = prompt
        if task == "triage":
            return {
                "question": "Does it fail for one site or all sites?",
                "why": "Separates DNS from routing.",
                "hypotheses": [{"title": "DNS failure", "why": "Nothing resolves."}],
                "next_check": "Read the DNS server list.",
                "unknowns": ["Which servers?"],
            }, []
        return None, []


def test_local_triage_prompt_carries_knowledge_block() -> None:
    state = InvestigationState(
        id="inv-m022-local",
        problem="DNS does not resolve on the field laptop",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "DNS does not resolve."}],
    )
    provider = _RecordingProvider()
    settings = Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="muse-spark-1.3",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )
    asyncio.run(_run_local_tasks(state, provider, settings, False))
    assert "triage" in provider.prompts
    assert "Reference excerpts" in provider.prompts["triage"]
    assert "ref-dns-triage" in provider.prompts["triage"]
