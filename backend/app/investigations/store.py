"""Investigation state objects over SQLite persistence.

Working state lives in InvestigationState; every mutation is saved to the
local database so history survives backend restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..schemas import (
    ActionExecution,
    ActionProposal,
    ActivityRecord,
    AnalysisResult,
    DiagnosticBundle,  # noqa: F401  (re-exported for convenience)
    EvidenceItem,
    EvidenceRefresh,
    InvestigationResponse,
    InvestigationSummary,
    RegressionCheck,
    ResolutionPlan,
    TechnicianNote,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class InvestigationState:
    id: str
    problem: str
    service_name: str | None
    has_image: bool
    messages: list[dict] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    activity: list[ActivityRecord] = field(default_factory=list)
    assessment: AnalysisResult | None = None
    warnings: list[str] = field(default_factory=list)
    status: str = "complete"
    tool_calls_made: int = 0
    ev_counter: int = 0
    seq_counter: int = 0
    mode: str = "simulated"
    model: str = ""
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    proposals: list[ActionProposal] = field(default_factory=list)
    executions: list[ActionExecution] = field(default_factory=list)
    notes: list[TechnicianNote] = field(default_factory=list)
    refreshes: list[EvidenceRefresh] = field(default_factory=list)
    plans: list[ResolutionPlan] = field(default_factory=list)
    regression_checks: list[RegressionCheck] = field(default_factory=list)

    def add_activity(
        self,
        kind: str,
        title: str,
        detail: str = "",
        tool_name: str | None = None,
        duration_ms: int | None = None,
        evidence_ids: list[str] | None = None,
    ) -> ActivityRecord:
        self.seq_counter += 1
        record = ActivityRecord(
            seq=self.seq_counter,
            kind=kind,  # type: ignore[arg-type]
            title=title,
            detail=detail,
            tool_name=tool_name,
            duration_ms=duration_ms,
            evidence_ids=evidence_ids or [],
        )
        self.activity.append(record)
        self.updated_at = _now()
        return record

    def add_evidence(
        self,
        category: str,
        source: str,
        data: dict,
        error: str | None = None,
        tool_name: str | None = None,
        tool_args: dict | None = None,
        refresh_of: str | None = None,
    ) -> EvidenceItem:
        self.ev_counter += 1
        item = EvidenceItem(
            id=f"ev-{self.ev_counter}",
            category=category,
            source=source,
            collected_at=_now(),
            data=data,
            error=error,
            tool_name=tool_name,
            tool_args=dict(tool_args) if tool_args is not None else None,
            refresh_of=refresh_of,
        )
        self.evidence.append(item)
        self.updated_at = _now()
        return item

    def add_refresh(
        self,
        old_evidence_id: str,
        new_evidence_id: str | None,
        tool_name: str,
        verdict: str,
        changes: list[str],
        old_collected_at,
        new_collected_at,
        affected_causes: list[str] | None = None,
    ) -> EvidenceRefresh:
        record = EvidenceRefresh(
            old_evidence_id=old_evidence_id,
            new_evidence_id=new_evidence_id,
            tool_name=tool_name,
            verdict=verdict,  # type: ignore[arg-type]
            changes=list(changes),
            old_collected_at=old_collected_at,
            new_collected_at=new_collected_at,
            compared_at=_now(),
            affected_causes=affected_causes or [],
        )
        self.refreshes.append(record)
        self.updated_at = _now()
        return record

    def known_evidence_ids(self) -> set[str]:
        return {item.id for item in self.evidence}

    def add_note(self, text: str) -> TechnicianNote:
        from uuid import uuid4

        note = TechnicianNote(
            note_id=f"note-{uuid4().hex[:8]}",
            text=text.strip(),
            created_at=_now(),
        )
        self.notes.append(note)
        self.updated_at = _now()
        return note

    def to_response(self, uses_fixtures: bool) -> InvestigationResponse:
        from ..analysis.contradictions import detect_contradictions
        from ..analysis.loop import MAX_TOOL_CALLS
        from ..analysis.rechecks import suggest_rechecks
        from ..config import load_settings

        contradictions = detect_contradictions(self.problem, list(self.evidence))
        try:
            ttl_s = load_settings().evidence_ttl_s
        except Exception:  # noqa: BLE001 - response shaping must not fail
            ttl_s = 900.0
        return InvestigationResponse(
            investigation_id=self.id,
            problem=self.problem,
            service_name=self.service_name,
            status=self.status,  # type: ignore[arg-type]
            created_at=self.created_at,
            uses_fixtures=uses_fixtures,
            analysis_mode=self.mode,  # type: ignore[arg-type]
            model=self.model,
            evidence=list(self.evidence),
            activity=list(self.activity),
            assessment=self.assessment,
            warnings=list(self.warnings),
            has_screenshot=self.has_image,
            proposals=list(self.proposals),
            executions=list(self.executions),
            notes=list(self.notes),
            refreshes=list(self.refreshes),
            plans=list(self.plans),
            regression_checks=list(self.regression_checks),
            contradictions=contradictions,
            suggested_rechecks=suggest_rechecks(self, ttl_s, MAX_TOOL_CALLS),
            tool_calls_used=self.tool_calls_made,
            tool_calls_max=MAX_TOOL_CALLS,
        )


class InvestigationStore:
    """Thin facade over SQLite persistence."""

    def create(
        self, problem: str, service_name: str | None, has_image: bool
    ) -> InvestigationState:
        from uuid import uuid4

        from . import persistence

        state = InvestigationState(
            id=f"inv-{uuid4().hex[:12]}",
            problem=problem,
            service_name=service_name,
            has_image=has_image,
        )
        persistence.save_state(state)
        return state

    def get(self, investigation_id: str) -> InvestigationState | None:
        from . import persistence

        return persistence.load_state(investigation_id)

    def save(self, state: InvestigationState) -> None:
        from . import persistence

        state.updated_at = _now()
        persistence.save_state(state)

    def list_recent(self, limit: int = 50) -> list[InvestigationSummary]:
        from . import persistence

        return [InvestigationSummary(**row) for row in persistence.list_states(limit)]


store = InvestigationStore()
