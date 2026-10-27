"""Analysis validation and simulated provider grounding."""

import asyncio
import json

import pytest

from app.analysis.provider import SimulatedProvider
from app.analysis.validate import ModelAnalysisError, validate_model_output
from app.config import Settings
from app.diagnostics import fixtures as fx
from app.diagnostics.collector import collect_diagnostics


def _settings() -> Settings:
    return Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="muse-spark-1.3",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )


GOOD_MODEL_OUTPUT = {
    "summary": "Service wuauserv is stopped.",
    "facts": [{"statement": "Status is Stopped.", "evidence_ids": ["ev-1"]}],
    "causes": [
        {
            "title": "Manual stop",
            "description": "May be intentional.",
            "likelihood": "medium",
            "evidence_ids": ["ev-1"],
        }
    ],
    "uncertainties": ["Whether the stop was intentional."],
    "missing_evidence": ["Runbook expectation."],
    "next_actions": ["Review the System log."],
    "explanation": "Test explanation.",
}


def test_simulated_analysis_is_grounded_in_bundle() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    analysis = fx.build_simulated_analysis(bundle)
    assert analysis.mode == "simulated"
    assert analysis.model == "fieldrook-simulated-001"
    known = {item.id for item in bundle.items}
    assert analysis.facts
    for fact in analysis.facts:
        assert set(fact.evidence_ids) <= known
    for cause in analysis.causes:
        assert cause.likelihood in ("high", "medium", "low")
        assert set(cause.evidence_ids) <= known
    blob = " ".join(
        [
            analysis.summary,
            analysis.explanation,
            *[fact.statement for fact in analysis.facts],
            *[cause.title + cause.description for cause in analysis.causes],
        ]
    ).lower()
    for banned in (
        "restarted the service",
        "executed",
        "resolved the issue",
        "fix has been applied",
    ):
        assert banned not in blob


def test_simulated_provider_returns_simulated_mode() -> None:
    bundle = collect_diagnostics("Spooler", _settings())
    analysis = asyncio.run(SimulatedProvider(_settings()).analyze(bundle))
    assert analysis.mode == "simulated"


def test_validate_good_model_output() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    analysis = validate_model_output(json.dumps(GOOD_MODEL_OUTPUT), bundle, "muse-spark-1.3")
    assert analysis.mode == "live"
    assert analysis.model == "muse-spark-1.3"
    assert analysis.facts[0].evidence_ids == ["ev-1"]
    assert analysis.validation_warnings == []


def test_validate_rejects_non_json() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    with pytest.raises(ModelAnalysisError):
        validate_model_output("not json at all", bundle, "muse-spark-1.3")


def test_validate_rejects_missing_keys() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    with pytest.raises(ModelAnalysisError):
        validate_model_output(json.dumps({"summary": "x"}), bundle, "muse-spark-1.3")


def test_validate_drops_unknown_evidence_refs_with_warning() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    payload = dict(GOOD_MODEL_OUTPUT)
    payload["facts"] = [
        {"statement": "Bogus ref.", "evidence_ids": ["ev-1", "ev-999"]},
    ]
    analysis = validate_model_output(json.dumps(payload), bundle, "muse-spark-1.3")
    assert analysis.facts[0].evidence_ids == ["ev-1"]
    assert len(analysis.validation_warnings) == 1
    assert "ev-999" in analysis.validation_warnings[0]


def test_validate_accepts_next_steps_and_derives_actions() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    payload = dict(GOOD_MODEL_OUTPUT)
    del payload["next_actions"]
    payload["next_steps"] = [
        {
            "step": "Check the task definition.",
            "why": "Evidence shows a suspect task.",
            "evidence_ids": ["ev-1", "ev-999"],
            "inspect": "Task Scheduler actions.",
            "confirms": "A wrong directory confirms it.",
            "impact": "read-only",
            "admin_maybe": True,
        },
        "Plain string step still accepted.",
        {"why": "Missing step text is dropped."},
    ]
    analysis = validate_model_output(json.dumps(payload), bundle, "muse-spark-1.3")
    assert analysis.next_actions[0] == "Check the task definition."
    assert analysis.next_steps[0].evidence_ids == ["ev-1"]
    assert analysis.next_steps[0].admin_maybe is True
    assert analysis.next_steps[1].step == "Plain string step still accepted."
    assert analysis.next_steps[1].impact == "unknown"
    assert any("malformed" in warning for warning in analysis.validation_warnings)
    assert any("ev-999" in warning for warning in analysis.validation_warnings)


def test_validate_rejects_missing_guidance() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    payload = dict(GOOD_MODEL_OUTPUT)
    del payload["next_actions"]
    with pytest.raises(ModelAnalysisError):
        validate_model_output(json.dumps(payload), bundle, "muse-spark-1.3")


def test_simulated_investigation_emits_runbook_steps() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    analysis = fx.build_simulated_investigation_analysis("Service looks odd.", bundle.items)
    assert analysis.next_steps
    assert [step.step for step in analysis.next_steps] == analysis.next_actions
    assert all(step.impact in ("read-only", "changes-system", "unknown") for step in analysis.next_steps)
    known = {item.id for item in bundle.items}
    for step in analysis.next_steps:
        assert set(step.evidence_ids) <= known
