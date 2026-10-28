"""Technician's memory endpoints (M009): library, matches, rechecks.

The library is local SQLite only. Nothing here sends stored incidents to
any model: matches are computed deterministically in-process, and the only
model contact is the technician-initiated "investigate this hypothesis"
follow-up, which carries a short templated prompt, never the library.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..config import load_settings
from ..investigations import persistence
from ..investigations.store import store
from ..knowledge import reference_service as refsvc, service as memory
from ..knowledge.service import KnowledgeBudgetError, KnowledgeError
from ..schemas import InvestigationResponse, KnowledgeEntry, KnowledgeMatch
from .actions import require_local_origin

router = APIRouter(tags=["knowledge"])


class RecordRequest(BaseModel):
    confirmed_cause: str = Field(default="", max_length=500)


def _all_entries() -> list[KnowledgeEntry]:
    return [KnowledgeEntry.model_validate_json(raw) for raw in persistence.list_knowledge_entries()]


@router.post(
    "/api/investigations/{investigation_id}/knowledge",
    response_model=KnowledgeEntry,
    dependencies=[Depends(require_local_origin)],
)
def record_knowledge(investigation_id: str, request: RecordRequest) -> Any:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    try:
        entry, created = memory.record_entry(
            state, request.confirmed_cause, _all_entries()
        )
    except KnowledgeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    persistence.save_knowledge_entry(entry.model_dump_json(), entry.entry_id)
    state.add_activity(
        "note",
        f"Saved to knowledge as {entry.entry_id}"
        + ("" if created else f" (merged, {entry.occurrence_count} occurrences)"),
        f"Outcome {entry.outcome}; {len(entry.criteria)} criteria stored.",
    )
    store.save(state)
    return Response(
        content=entry.model_dump_json(),
        media_type="application/json",
        status_code=201 if created else 200,
    )


@router.get("/api/knowledge", response_model=list[KnowledgeEntry])
def list_knowledge(
    q: str = Query(default="", max_length=200),
    category: str = Query(default="", max_length=64),
    outcome: str = Query(default="", max_length=32),
) -> list[KnowledgeEntry]:
    entries = _all_entries()
    needle = q.strip().lower()
    if needle:
        entries = [
            e
            for e in entries
            if needle in e.problem.lower()
            or needle in " ".join(e.symptoms)
            or (e.identity or "") == needle
        ]
    if category:
        entries = [e for e in entries if e.category == category]
    if outcome:
        entries = [e for e in entries if e.outcome == outcome]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


@router.get("/api/knowledge/{entry_id}", response_model=KnowledgeEntry)
def get_knowledge(entry_id: str) -> KnowledgeEntry:
    raw = persistence.load_knowledge_entry(entry_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge entry {entry_id!r}.")
    return KnowledgeEntry.model_validate_json(raw)


@router.delete(
    "/api/knowledge/{entry_id}",
    dependencies=[Depends(require_local_origin)],
)
def delete_knowledge(entry_id: str) -> dict[str, str]:
    if not persistence.delete_knowledge_entry(entry_id):
        raise HTTPException(status_code=404, detail=f"Unknown knowledge entry {entry_id!r}.")
    return {"deleted": entry_id}


@router.get("/api/knowledge/{entry_id}/export")
def export_knowledge(entry_id: str, format: str = "markdown") -> Response:
    raw = persistence.load_knowledge_entry(entry_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge entry {entry_id!r}.")
    entry = KnowledgeEntry.model_validate_json(raw)
    if format == "json":
        return Response(content=entry.model_dump_json(indent=2), media_type="application/json")
    if format != "markdown":
        raise HTTPException(status_code=400, detail="format must be markdown or json.")
    lines = [
        f"# Knowledge entry {entry.entry_id}",
        "",
        f"Problem: {entry.problem}",
        f"Category: {entry.category} | Outcome: {entry.outcome}",
        f"Identity: {entry.identity or '(none)'} | Event codes: {', '.join(entry.event_codes) or '(none)'}",
        f"Symptoms: {', '.join(entry.symptoms) or '(none)'}",
        "",
        "## Evidence signature",
        "",
    ]
    for category, value in sorted(entry.evidence_signature.items()):
        lines.append(f"- {category}: {value}")
    lines += [
        "",
        f"Root cause: {entry.root_cause or '(not established)'}"
        + (" (technician-confirmed)" if entry.root_cause_verified else " (INFERRED hypothesis)"),
        f"Intervention ({entry.intervention_kind}): {entry.intervention or '(none)'}",
        "",
        "## Measured criteria",
        "",
    ]
    for criterion in entry.criteria:
        before = entry.baseline_values.get(criterion.criterion_id)
        after = entry.verified_values.get(criterion.criterion_id)
        lines.append(
            f"- {criterion.description} [{criterion.tool_name} {criterion.path} "
            f"{criterion.op} {criterion.expected}] before {before!r} -> after {after!r}"
        )
    if not entry.criteria:
        lines.append("(no measured criteria)")
    lines += [
        "",
        f"Verified: {entry.verified_at or '(never)'} | Recorded: {entry.created_at} "
        f"| Occurrences: {entry.occurrence_count}",
        f"Source: investigation {entry.source_investigation_id}"
        + (f", plan {entry.source_plan_id}" if entry.source_plan_id else ""),
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/markdown")


@router.get(
    "/api/investigations/{investigation_id}/knowledge/matches",
    response_model=dict[str, list[KnowledgeMatch]],
)
def knowledge_matches(
    investigation_id: str, limit: int = Query(default=5, ge=1, le=20)
) -> dict[str, list[KnowledgeMatch]]:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    entries = [e for e in _all_entries() if e.source_investigation_id != state.id]
    matches = memory.match_entries(
        state.problem, state.service_name, list(state.evidence), entries, limit
    )
    return {"matches": matches}


@router.post(
    "/api/investigations/{investigation_id}/knowledge/{entry_id}/recheck",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
async def recheck_knowledge(investigation_id: str, entry_id: str) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    raw = persistence.load_knowledge_entry(entry_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge entry {entry_id!r}.")
    entry = KnowledgeEntry.model_validate_json(raw)
    settings = load_settings()
    try:
        await memory.recheck_entry(state, entry, settings)
    except KnowledgeBudgetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KnowledgeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store.save(state)
    uses_fixtures = state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)

@router.get(
    "/api/investigations/{investigation_id}/knowledge/references",
)
def knowledge_references(
    investigation_id: str, limit: int = Query(default=5, ge=1, le=20)
) -> dict[str, Any]:
    """Ranked reference excerpts for an investigation (FORGE 1D, read-only).

    Case memory and reference docs never merge: this returns background
    reading with citations, never KnowledgeMatch entries and never a
    diagnosis. Text reaches the model only as quoted excerpts.
    """
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    terms: list[str] = []
    for ev in state.evidence:
        terms.append(ev.category)
        if ev.tool_name:
            terms.append(ev.tool_name)
    # Same split as loop.reference_excerpts_for: corpus prose holds
    # 'dns', not 'dns_config'.
    split_terms: list[str] = []
    for term in terms:
        split_terms.extend(part for part in re.split(r"[^a-z0-9]+", term.lower()) if len(part) >= 3)
    terms = sorted(set(terms + split_terms))[:40]
    passages = refsvc.match_references(state.problem, state.service_name, terms, limit)
    return {
        "passages": [p.model_dump() for p in passages],
        "citations": [c.model_dump() for c in refsvc.build_citations(passages)],
        "message": refsvc.build_technician_message(passages, state.problem),
    }
