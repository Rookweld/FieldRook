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
