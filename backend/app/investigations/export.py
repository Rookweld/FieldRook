"""Incident report export: Markdown for tickets, JSON for machines.

Exports distinguish observed facts from AI interpretation and never include
screenshot bytes, API credentials, or approval tokens.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _export_dict(state: Any) -> dict[str, Any]:
    # to_response excludes chat messages, so no image bytes can leak into exports.
    response = state.to_response(uses_fixtures=(state.mode == "simulated"))
    data = response.model_dump(mode="json")
    data["exported_at"] = datetime.now(timezone.utc).isoformat()
    return data


def build_json(state: Any) -> str:
    return json.dumps(_export_dict(state), indent=2)


def build_markdown(state: Any) -> str:
    data = _export_dict(state)
    lines: list[str] = []
    add = lines.append
    assessment = data.get("assessment") or {}
    add(f"# FieldRook incident report — {data['investigation_id']}")
    add("")
    add("## 1. Incident summary")
    add(assessment.get("summary", "(no assessment)") or "(no assessment)")
    add("")
    add("## 2. Initial technician report")
    add(data.get("problem", ""))
    if data.get("service_name"):
        add(f"Suspected service: {data['service_name']}")
    if data.get("has_screenshot"):
        add("A screenshot was attached (image bytes are never stored or exported).")
    add("")
    add("## 3. Investigation timeline")
    for record in data.get("activity", []):
        add(f"- #{record['seq']} [{record['kind']}] {record['title']}")
        if record.get("detail"):
            add(f"  {record['detail']}")
    add("")
    add("## 4. Collected evidence")
    for item in data.get("evidence", []):
        add(f"### {item['id']} — {item['category']} ({item['source']})")
        if item.get("error"):
            add(f"Collection error: {item['error']}")
        else:
            add("```json")
            add(json.dumps(item.get("data", {}), indent=2, default=str)[:4000])
            add("```")
    add("")
    add("## 5. AI-generated hypotheses (INFERRED — verify before acting)")
    for cause in assessment.get("causes", []):
        refs = ", ".join(cause.get("evidence_ids", []))
        add(f"- [{cause.get('likelihood')}] {cause.get('title')} (refs: {refs})")
        add(f"  {cause.get('description', '')}")
    add("")
    add("## 6. Proposed corrective actions")
    for proposal in data.get("proposals", []):
        add(f"- {proposal['proposal_id']}: {proposal['action_id']} on {proposal['target']} — {proposal['status']}")
        add(f"  Reason: {proposal.get('reason', '')}")
    if not data.get("proposals"):
        add("(none)")
    add("")
    add("## 7. Human approval decisions")
    for proposal in data.get("proposals", []):
        add(f"- {proposal['proposal_id']}: {proposal.get('decision') or 'pending'} at {proposal.get('decided_at') or '-'}")
    if not data.get("proposals"):
        add("(none)")
    add("")
    add("## 8. Actual execution records")
    for execution in data.get("executions", []):
        add(f"- {execution['execution_id']} ({execution['proposal_id']}): {execution.get('outcome')}")
        if execution.get("error"):
            add(f"  Error: {execution['error']}")
    if not data.get("executions"):
        add("(none)")
    add("")
    add("## 9. Before/after evidence")
    for execution in data.get("executions", []):
        add(f"### {execution['execution_id']}")
        add("Before:")
        add("```json")
        add(json.dumps(execution.get("before_state", {}), indent=2, default=str)[:2000])
        add("```")
        add("After:")
        add("```json")
        add(json.dumps(execution.get("after_state", {}), indent=2, default=str)[:2000])
        add("```")
    add("")
    outcomes = [e.get("outcome") for e in data.get("executions", [])]
    add("## 10. Final verified outcome")
    if outcomes:
        add(outcomes[-1])
    else:
        add("UNRESOLVED - investigated; no verified correction.")
        add(assessment.get("summary") or "No assessment recorded.")
    add("")
    add("## 11. Remaining uncertainty")
    for item in list(assessment.get("uncertainties", [])) + list(assessment.get("missing_evidence", [])):
        add(f"- {item}")
    if not assessment.get("uncertainties") and not assessment.get("missing_evidence"):
        add("(none recorded)")
    add("")
    add("## 12. Technician next steps (INFERRED guidance — manual, verify first)")
    steps = assessment.get("next_steps", []) or [
        {"step": text} for text in assessment.get("next_actions", [])
    ]
    for index, entry in enumerate(steps, 1):
        add(f"### 12.{index} {entry.get('step', '')}")
        if entry.get("why"):
            add(f"Why: {entry['why']}")
        if entry.get("evidence_ids"):
            add(f"Evidence: {', '.join(entry['evidence_ids'])}")
        if entry.get("inspect"):
            add(f"Inspect: {entry['inspect']}")
        if entry.get("confirms"):
            add(f"Confirms/weaken: {entry['confirms']}")
        impact = entry.get("impact", "unknown") or "unknown"
        admin = " (may need admin)" if entry.get("admin_maybe") else ""
        add(f"Impact: {impact}{admin}")
    if not steps:
        add("(none recorded)")
    add("")
    add("## 13. Technician notes")
    for note in data.get("notes", []):
        add(f"- [{note.get('created_at', '')}] {note.get('text', '')}")
    if not data.get("notes"):
        add("(none)")
    add("")
    add("## 14. Evidence refresh history")
    add("Historical items are preserved; each re-check below compares the old reading with the new one.")
    for refresh in data.get("refreshes", []):
        add(f"### {refresh['old_evidence_id']} -> {refresh.get('new_evidence_id') or '(collection failed)'}: {refresh['verdict'].upper()}")
        add(f"Tool: {refresh['tool_name']}")
        add(f"Historical: {refresh['old_collected_at']} — Current: {refresh.get('new_collected_at') or '-'} — Compared: {refresh['compared_at']}")
        for change in refresh.get("changes", []):
            add(f"- {change}")
        if refresh.get("affected_causes"):
            add(f"Hypotheses built on the old reading: {', '.join(refresh['affected_causes'])}")
    if not data.get("refreshes"):
        add("(no re-checks performed)")
    add("")
    add("---")
    add(f"Exported {data['exported_at']} by FieldRook. OBSERVED facts are measured; INFERRED causes are hypotheses.")
    return "\n".join(lines) + "\n"
