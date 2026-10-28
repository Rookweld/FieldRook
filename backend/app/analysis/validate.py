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
    SuggestedHypothesis,
    SuggestedPlan,
    SuggestedPlanStep,
    SuggestedQuestion,
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
MAX_SUGGESTED_HYPOTHESES = 8
MAX_SUGGESTED_PLAN_STEPS = 6
MAX_SUGGESTED_QUESTIONS = 2


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


def _known_only(ids: list[str], known_ids: set[str]) -> tuple[list[str], list[str]]:
    kept = [eid for eid in ids if eid in known_ids]
    dropped = [eid for eid in ids if eid not in known_ids]
    return kept, dropped


def _parse_suggested_hypotheses(
    raw: Any, known_ids: set[str]
) -> tuple[list[SuggestedHypothesis], list[str]]:
    """Parse optional model-proposed hypotheses leniently (M016)."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["Dropped malformed hypotheses (not a list)."]
    parsed: list[SuggestedHypothesis] = []
    dropped = 0
    filtered_ids = 0
    for entry in raw[:MAX_SUGGESTED_HYPOTHESES]:
        try:
            item = SuggestedHypothesis.model_validate(entry)
        except ValidationError:
            dropped += 1
            continue
        item.supporting_evidence_ids, dropped_support = _known_only(
            list(item.supporting_evidence_ids), known_ids
        )
        item.contradicting_evidence_ids, dropped_contra = _known_only(
            list(item.contradicting_evidence_ids), known_ids
        )
        filtered_ids += len(dropped_support) + len(dropped_contra)
        parsed.append(item)
    warnings: list[str] = []
    if len(raw) > MAX_SUGGESTED_HYPOTHESES:
        warnings.append(
            f"Kept the first {MAX_SUGGESTED_HYPOTHESES} suggested hypotheses; dropped the rest."
        )
    if dropped:
        warnings.append(f"Dropped {dropped} malformed suggested hypothesis entries.")
    if filtered_ids:
        warnings.append(
            f"Dropped {filtered_ids} suggested-hypothesis evidence reference(s) not in the bundle."
        )
    return parsed, warnings


def _parse_suggested_plan(raw: Any) -> tuple[SuggestedPlan | None, list[str]]:
    """Parse an optional model-proposed troubleshooting plan leniently (M016).

    AUTOMATED_READ_ONLY steps naming an unknown tool are downgraded to
    TECHNICIAN_CHECK guidance: the model proposes direction, the registry
    decides what FieldRook may execute.
    """
    if raw is None:
        return None, []
    steps_raw = raw.get("steps") if isinstance(raw, dict) else raw
    if not isinstance(steps_raw, list):
        return None, ["Dropped malformed plan (steps is not a list)."]
    from ..tools.registry import REGISTRY

    steps: list[SuggestedPlanStep] = []
    warnings: list[str] = []
    dropped = 0
    for entry in steps_raw[:MAX_SUGGESTED_PLAN_STEPS]:
        try:
            step = SuggestedPlanStep.model_validate(entry)
        except ValidationError:
            dropped += 1
            continue
        if step.tool_name and step.tool_name not in REGISTRY:
            warnings.append(
                f"Step {step.instruction[:60]!r} names unknown tool "
                f"{step.tool_name!r}; kept as technician guidance."
            )
            if step.kind == "AUTOMATED_READ_ONLY":
                step.kind = "TECHNICIAN_CHECK"
            step.tool_name = None
        steps.append(step)
    if len(steps_raw) > MAX_SUGGESTED_PLAN_STEPS:
        warnings.append(
            f"Kept the first {MAX_SUGGESTED_PLAN_STEPS} suggested plan steps; dropped the rest."
        )
    if dropped:
        warnings.append(f"Dropped {dropped} malformed suggested plan step(s).")
    if not steps:
        return None, warnings
    return SuggestedPlan(steps=steps), warnings


def _parse_suggested_questions(raw: Any) -> tuple[list[SuggestedQuestion], list[str]]:
    """Parse optional model-proposed clarifying questions leniently (M016)."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["Dropped malformed questions (not a list)."]
    parsed: list[SuggestedQuestion] = []
    dropped = 0
    for entry in raw[:MAX_SUGGESTED_QUESTIONS]:
        try:
            item = SuggestedQuestion.model_validate(entry)
        except ValidationError:
            dropped += 1
            continue
        if not item.question.strip():
            dropped += 1
            continue
        parsed.append(item)
    warnings: list[str] = []
    if len(raw) > MAX_SUGGESTED_QUESTIONS:
        warnings.append(
            f"Kept the first {MAX_SUGGESTED_QUESTIONS} suggested questions; dropped the rest."
        )
    if dropped:
        warnings.append(f"Dropped {dropped} malformed suggested question(s).")
    return parsed, warnings


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
    suggested_hypotheses, hyp_warnings = _parse_suggested_hypotheses(
        data.get("hypotheses"), known_ids
    )
    suggested_plan, plan_warnings = _parse_suggested_plan(data.get("plan"))
    suggested_questions, question_warnings = _parse_suggested_questions(data.get("questions"))
    understanding = data.get("understanding")
    understanding_text = str(understanding).strip()[:2000] if understanding is not None else ""
    provider_label = data.get("provider")
    provider_text = str(provider_label).strip()[:120] if provider_label is not None else ""
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
            understanding=understanding_text,
            provider=provider_text,
            suggested_hypotheses=suggested_hypotheses,
            suggested_plan=suggested_plan,
            suggested_questions=suggested_questions,
        )
    except ValidationError as exc:
        raise ModelAnalysisError(f"Model output failed schema validation: {exc}") from exc
    result.validation_warnings.extend(step_warnings)
    result.validation_warnings.extend(hyp_warnings)
    result.validation_warnings.extend(plan_warnings)
    result.validation_warnings.extend(question_warnings)

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
