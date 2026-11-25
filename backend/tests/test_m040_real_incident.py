"""M040 regression checks for grounded real-incident handling.

All inputs are redacted excerpts from an actual technician-led investigation.
No network, host diagnostic commands, or model service is needed.
"""

from __future__ import annotations

import asyncio
import json

from app.analysis.assist import (
    _already_answered_in_reports,
    _settle_questions,
    merge_questions,
)
from app.analysis.loop import _run_local_tasks
from app.analysis.technical_signals import (
    excluded_port_from_reports,
    reported_context,
    reported_failure_layers,
)
from app.analysis.validate import validate_assessment_output
from app.config import Settings
from app.investigations.store import InvestigationState
from app.schemas import ClarifyingQuestion, Hypothesis


INTAKE = (
    "The launcher briefly indicates ONLINE but switches OFFLINE within "
    "seconds. The launcher stays open; the tunnel subprocess disappears."
)
QUESTION_ALREADY_ANSWERED = (
    "Does the launcher briefly show ONLINE before switching OFFLINE, "
    "and does it stay open?"
)
MODULE = (
    "Technician observation: ConvertTo-SecureString raised error: "
    "Microsoft.PowerShell.Security module could not be loaded."
)
PROFILE = (
    "Technician observation: stderr says cannot find YAML profile under "
    ".config/tunnel-client; the file exists in AppData/Roaming."
)
PORT = (
    "Technician observation: listen tcp 127.0.0.1:8080: bind: "
    "An attempt was made to access a socket in a way forbidden by its "
    "access permissions. No process is listening on port 8080. "
    "Windows TCP excluded port range 8019-8118. Port 18080 bound successfully."
)


def _state(problem: str = INTAKE, target: str = "remote") -> InvestigationState:
    return InvestigationState(
        id="m040-real-test", problem=problem, service_name=None,
        has_image=False, target=target,
        messages=[{"role": "user", "content": problem}],
    )


def _assessment_with_questions(*questions: str):
    return validate_assessment_output(
        json.dumps({
            "summary": "Reported problem under review.",
            "facts": [], "causes": [], "uncertainties": [],
            "missing_evidence": [], "next_actions": [], "explanation": "",
            "questions": [{"question": q, "why": "Further information"} for q in questions],
        }),
        set(), "local/mocked", "live",
    )


def test_real_incident_excluded_port_mathematical_overlap() -> None:
    result = excluded_port_from_reports([PORT])
    assert result is not None
    assert (result.port, result.range_start, result.range_end) == (8080, 8019, 8118)
    assert result.no_listener_reported
    assert "technician" in result.display_note().lower()
    assert "not a FieldRook measurement" in result.display_note()
    assert "reservation" in result.prompt_note()


def test_excluded_port_needs_denied_bind_and_same_report() -> None:
    assert excluded_port_from_reports(["Windows TCP excluded port range 8019-8118."]) is None
    assert excluded_port_from_reports([
        "Connection refused on port 8080. Excluded port range 8019-8118."
    ]) is None
    assert excluded_port_from_reports([
        "Port 8080 bind: access denied.",
        "Excluded port range 8019-8118."
    ]) is None


def test_excluded_port_range_must_include_failed_port() -> None:
    assert excluded_port_from_reports([
        "listen tcp 127.0.0.1:9000: bind: access denied. "
        "Windows excluded port range 8019-8118."
    ]) is None
    assert excluded_port_from_reports([
        "listen tcp 127.0.0.1:8080: bind: access denied. "
        "Windows excluded port range 9000-9100."
    ]) is None
    assert excluded_port_from_reports([
        "listen tcp 127.0.0.1:8080: bind: access denied. "
        "Windows excluded port range 8118-8019."
    ]) is None


def test_chronological_layer_summary_is_report_only() -> None:
    layers = reported_failure_layers([MODULE, PROFILE, PORT])
    assert len(layers) == 3, layers
    assert "module" in layers[0].lower()
    assert "profile" in layers[1].lower()
    assert "TCP" in layers[2]
    summary = reported_context([MODULE, PROFILE, PORT])
    assert "technician reports" in summary
    assert "not independent" in summary
    assert "8019-8118" in summary
    assert "independently verify" in summary


def test_unrelated_report_creates_no_assumed_diagnosis() -> None:
    assert reported_context(["A printer stopped printing."]) == ""
    assert reported_failure_layers(["Windows firewall is on."]) == ()


def test_initial_yes_no_question_already_answered() -> None:
    state = _state()
    assert _already_answered_in_reports(state, QUESTION_ALREADY_ANSWERED)


def test_initial_open_ended_comparison_is_not_falsely_suppressed() -> None:
    state = _state(
        "Teams files fail from the desktop app; local Excel files open."
    )
    assert not _already_answered_in_reports(
        state, "Does the same document open in Teams web from the affected user account?"
    )
    assert not _already_answered_in_reports(
        state, "Why did this problem start yesterday?"
    )


def test_known_remote_target_does_not_need_machine_scope_again() -> None:
    assert _already_answered_in_reports(
        _state(target="remote"),
        "Which computer is affected (this host or another machine)?"
    )
    assert not _already_answered_in_reports(
        _state(target="unknown"),
        "Which computer is affected (this host or another machine)?"
    )


def test_error_text_question_waits_until_actual_error_supplied() -> None:
    state = _state()
    q = "Can you provide or check the following: Exact error text or code from the affected computer."
    assert not _already_answered_in_reports(state, q)
    state.messages.append({"role": "user", "content": MODULE})
    assert _already_answered_in_reports(state, q)


def test_questions_in_intake_withheld_before_asking_again() -> None:
    state = _state()
    state.assessment = _assessment_with_questions(
        QUESTION_ALREADY_ANSWERED,
        "Does this issue also happen on the neighbour's computer?"
    )
    added, withheld = merge_questions(state, 1)
    assert len(added) == 1
    assert len(withheld) == 1
    assert state.questions[0].question.endswith("neighbour's computer?")


def test_stale_question_retired_after_explicit_new_observation() -> None:
    state = _state()
    state.questions.append(
        ClarifyingQuestion(
            question_id="q-1", question=QUESTION_ALREADY_ANSWERED,
            source="model", status="open", asked_round=1,
        )
    )
    notes = _settle_questions(state, 2, [])
    assert notes
    assert state.questions[0].status == "retired"
    assert "report" in state.questions[0].retired_note.lower()


class _ObservingModel:
    name = "local"
    last_stats = {"wall_s": 0.1, "eval_count": 17, "eval_duration_s": 0.1}

    def __init__(self):
        self.prompts: list[str] = []

    def model_label(self) -> str:
        return "local/m040-mock"

    def capabilities(self):
        from app.analysis.provider import ProviderCapabilities
        return ProviderCapabilities(
            text=True, vision=False, tool_calling=False,
            structured_output=False, processing_location="local",
        )

    async def run_task(self, task, prompt, **kwargs):
        self.prompts.append(prompt)
        assert task == "reassess"
        # Intentionally weak model conclusion — deterministic report-only
        # correlation must remain visible, without pretending AI inferred it.
        return {
            "verdict": "Perhaps the firewall is preventing the application from starting.",
            "weakened": [],
            "next_step": "Check if another process is listening on port 8080.",
        }, []


def test_local_pipeline_displays_grounded_report_even_when_model_misses_it() -> None:
    settings = Settings(
        model_api_key=None, model_base_url="https://api.meta.ai/v1",
        model_name="m", fixtures_mode="never",
        command_timeout_s=2, model_timeout_s=3,
        info_gain_mode="observe",
    )
    state = _state()
    state.hypotheses.append(
        Hypothesis(hypothesis_id="hyp-1", title="Unverified startup failure")
    )
    for text in (MODULE, PROFILE, PORT):
        state.messages.append({"role": "user", "content": text})
    provider = _ObservingModel()
    asyncio.run(_run_local_tasks(state, provider, settings, True))
    assert len(provider.prompts) == 1
    assert "excluded Windows TCP port interval 8019-8118" in provider.prompts[0]
    assert state.assessment is not None
    assert "Technician-reported port evidence" in state.assessment.understanding
    assert "PowerShell module import failed" in state.assessment.understanding
    assert "configuration/profile lookup failed" in state.assessment.understanding
    assert state.tool_calls_made == 0, "remote incident never reads the Fury host"
    assert not state.proposals
    assert any(a.title == "Reported diagnostic correlation" for a in state.activity)
