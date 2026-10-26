"""Session-scoped investigation state.

Keeps the original symptoms, message history, collected evidence, tool-call
records, and conclusions for each investigation so follow-up requests can
continue without starting over. In-memory only: state is lost on restart.
This is deliberately not a persistent memory platform yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from ..schemas import (
    ActivityRecord,
    AnalysisResult,
    DiagnosticBundle,  # noqa: F401  (re-exported for convenience)
    EvidenceItem,
    InvestigationResponse,
)

MAX_SESSIONS = 50


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
    ) -> EvidenceItem:
        self.ev_counter += 1
        item = EvidenceItem(
            id=f"ev-{self.ev_counter}",
            category=category,
            source=source,
            collected_at=_now(),
            data=data,
            error=error,
        )
        self.evidence.append(item)
        self.updated_at = _now()
        return item

    def known_evidence_ids(self) -> set[str]:
        return {item.id for item in self.evidence}

    def to_response(self, uses_fixtures: bool) -> InvestigationResponse:
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
        )


class InvestigationStore:
    def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
        self._max_sessions = max_sessions
        self._data: dict[str, InvestigationState] = {}

    def create(
        self, problem: str, service_name: str | None, has_image: bool
    ) -> InvestigationState:
        state = InvestigationState(
            id=f"inv-{uuid4().hex[:12]}",
            problem=problem,
            service_name=service_name,
            has_image=has_image,
        )
        self._data[state.id] = state
        while len(self._data) > self._max_sessions:
            oldest = min(self._data.values(), key=lambda s: s.updated_at)
            del self._data[oldest.id]
        return state

    def get(self, investigation_id: str) -> InvestigationState | None:
        return self._data.get(investigation_id)


store = InvestigationStore()
