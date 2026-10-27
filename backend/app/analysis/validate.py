"""Validation of model-produced analysis output."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ..schemas import (
    AnalysisMode,
    AnalysisResult,
    DiagnosticBundle,
    ProposedAction,
    RunbookStep,
)


class ModelAnalysisError(RuntimeError):
    """Raised when a model call fails or its output is unusable."""


REQUIRED_KEYS = (
    "summary",
    "facts",
    "causes",
    "uncertainties",
    "missing_evidence",
    "explanation",
)

MAX_RUNBOOK_STEPS = 8


def _extract_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ModelAnalysisError("Model did not return valid JSON.")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ModelAnalysisError(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ModelAnalysisError("Model output must be a JSON object.")
    return data


def _parse_runbook_steps(raw: Any) -> tuple[list[RunbookStep], list[str]]:
    """Parse optional structured next steps leniently.

    Guidance must never sink an assessment: malformed entries are dropped
    with a warning instead of failing validation.
    """
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["Dropped malformed next_steps (not a list); kept next_actions text."]
    steps: list[RunbookStep] = []
    dropped = 0
    for entry in raw[:MAX_RUNBOOK_STEPS]:
        if isinstance(entry, str):
            entry = {"step": entry}
        try:
            steps.append(RunbookStep.model_validate(entry))
        except ValidationError:
            dropped += 1
    warnings: list[str] = []
    if isinstance(raw, list) and len(raw) > MAX_RUNBOOK_STEPS:
        warnings.append(f"Kept the first {MAX_RUNBOOK_STEPS} runbook steps; dropped the rest.")
    if dropped:
        warnings.append(f"Dropped {dropped} malformed runbook step(s).")
    return steps, warnings


def validate_assessment_output(
    raw: str, known_ids: set[str], model: str, mode: AnalysisMode
) -> AnalysisResult:
    """Validate assessment JSON against a set of known evidence ids."""
    data = _extract_json(raw)
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ModelAnalysisError(f"Model output is missing keys: {', '.join(missing)}.")
    if "next_actions" not in data and "next_steps" not in data:
        raise ModelAnalysisError("Model output needs next_actions or next_steps guidance.")
    steps, step_warnings = _parse_runbook_steps(data.get("next_steps"))
    actions = data.get("next_actions")
    if actions is None:
        actions = [step.step for step in steps]
    try:
        result = AnalysisResult(
            summary=data["summary"],
            facts=data["facts"],
            causes=data["causes"],
            uncertainties=data["uncertainties"],
            missing_evidence=data["missing_evidence"],
            next_actions=actions,
            next_steps=steps,
            explanation=data["explanation"],
            mode=mode,
            model=model,
        )
    except ValidationError as exc:
        raise ModelAnalysisError(f"Model output failed schema validation: {exc}") from exc
    result.validation_warnings.extend(step_warnings)

    dropped: list[str] = []
    for fact in result.facts:
        kept = [eid for eid in fact.evidence_ids if eid in known_ids]
        dropped.extend(eid for eid in fact.evidence_ids if eid not in known_ids)
        fact.evidence_ids = kept
    for cause in result.causes:
        kept = [eid for eid in cause.evidence_ids if eid in known_ids]
        dropped.extend(eid for eid in cause.evidence_ids if eid not in known_ids)
        cause.evidence_ids = kept
    for step in result.next_steps:
        kept = [eid for eid in step.evidence_ids if eid in known_ids]
        dropped.extend(eid for eid in step.evidence_ids if eid not in known_ids)
        step.evidence_ids = kept
    if dropped:
        unique = ", ".join(sorted(set(dropped)))
        result.validation_warnings.append(
            f"Dropped {len(dropped)} evidence reference(s) not present in the bundle: "
            f"{unique}."
        )
    uncited = [fact for fact in result.facts if not fact.evidence_ids]
    if uncited:
        result.validation_warnings.append(
            f"{len(uncited)} fact(s) cite no evidence; treat them as unverified."
        )
    proposed = data.get("proposed_action")
    if proposed is not None:
        try:
            action = ProposedAction.model_validate(proposed)
        except ValidationError:
            result.validation_warnings.append(
                "Dropped a malformed proposed_action; no correction was proposed."
            )
        else:
            kept = [eid for eid in action.evidence_ids if eid in known_ids]
            dropped_refs = [eid for eid in action.evidence_ids if eid not in known_ids]
            if dropped_refs:
                result.validation_warnings.append(
                    f"Dropped {len(dropped_refs)} proposed-action evidence reference(s) not in the bundle."
                )
            action.evidence_ids = kept
            result.proposed_action = action
    return result


def validate_model_output(raw: str, bundle: DiagnosticBundle, model: str) -> AnalysisResult:
    """Validate M001 single-service assessment output (live mode)."""
    return validate_assessment_output(
        raw, {item.id for item in bundle.items}, model, "live"
    )
