"""Prompt construction for the Meta Model API.

The model receives structured observations and must return strict JSON.
Grounding rules forbid inventing evidence or claiming actions were taken.
"""

from __future__ import annotations

import json

from ..schemas import DiagnosticBundle

SYSTEM_PROMPT = """You are FieldRook, an evidence-driven troubleshooting assistant for IT technicians.

You analyze Windows service diagnostic bundles. Distinguish strictly between:
- OBSERVED: values present in the bundle. Restate them with evidence ids.
- INFERRED: hypotheses consistent with the evidence. Label them as hypotheses.
- UNVERIFIED: what the bundle cannot prove. List it as uncertainty or missing evidence.

Rules:
- Return ONLY a JSON object with the requested keys. No prose, no markdown fences.
- Never invent evidence, timestamps, services, or event-log entries.
- Cite only evidence ids that appear in the bundle.
- Never claim any diagnostic or corrective action was taken.
- Never present a hypothesis as a verified fact.
- Recommended actions must be read-only diagnostic steps, never destructive."""


def build_messages(bundle: DiagnosticBundle) -> list[dict[str, str]]:
    payload = bundle.model_dump(mode="json")
    user_content = (
        "Analyze this Windows service diagnostic bundle and return ONLY a JSON object "
        "with keys: summary, facts, causes, uncertainties, missing_evidence, "
        "next_actions, explanation.\n\n"
        "Schema:\n"
        "- summary: 1-2 sentence incident summary.\n"
        "- facts: [{statement, evidence_ids}] restating observed values.\n"
        "- causes: [{title, description, likelihood (high|medium|low), evidence_ids}] "
        "hypotheses only.\n"
        "- uncertainties: [string] what cannot be concluded.\n"
        "- missing_evidence: [string] what else to collect.\n"
        "- next_actions: [string] read-only diagnostic steps only.\n"
        "- explanation: short paragraph for the technician.\n\n"
        f"BUNDLE:\n{json.dumps(payload)}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
