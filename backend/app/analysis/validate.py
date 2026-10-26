"""Validation of model-produced analysis output."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ..schemas import AnalysisResult, DiagnosticBundle


class ModelAnalysisError(RuntimeError):
    """Raised when a model call fails or its output is unusable."""


REQUIRED_KEYS = (
    "summary",
    "facts",
    "causes",
    "uncertainties",
    "missing_evidence",
    "next_actions",
    "explanation",
)


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


def validate_model_output(raw: str, bundle: DiagnosticBundle, model: str) -> AnalysisResult:
    data = _extract_json(raw)
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ModelAnalysisError(f"Model output is missing keys: {', '.join(missing)}.")
    try:
        result = AnalysisResult(
            summary=data["summary"],
            facts=data["facts"],
            causes=data["causes"],
            uncertainties=data["uncertainties"],
            missing_evidence=data["missing_evidence"],
            next_actions=data["next_actions"],
            explanation=data["explanation"],
            mode="live",
            model=model,
        )
    except ValidationError as exc:
        raise ModelAnalysisError(f"Model output failed schema validation: {exc}") from exc

    known = {item.id for item in bundle.items}
    dropped: list[str] = []
    for fact in result.facts:
        kept = [eid for eid in fact.evidence_ids if eid in known]
        dropped.extend(eid for eid in fact.evidence_ids if eid not in known)
        fact.evidence_ids = kept
    for cause in result.causes:
        kept = [eid for eid in cause.evidence_ids if eid in known]
        dropped.extend(eid for eid in cause.evidence_ids if eid not in known)
        cause.evidence_ids = kept
    if dropped:
        unique = ", ".join(sorted(set(dropped)))
        result.validation_warnings.append(
            f"Dropped {len(dropped)} evidence reference(s) not present in the bundle: "
            f"{unique}."
        )
    return result
