"""Pydantic schemas for evidence, analysis, and incident assessments."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Likelihood = Literal["high", "medium", "low"]
BundleMode = Literal["live", "fixture"]
AnalysisMode = Literal["live", "simulated"]
ActivityKind = Literal[
    "plan",
    "tool_request",
    "tool_result",
    "evidence",
    "note",
    "done",
    "error",
    "reverify",
    "proposed",
    "approval_requested",
    "approved",
    "rejected",
    "executed",
    "verification_started",
    "verified",
]
InvestigationStatus = Literal["complete", "partial", "error"]
ActionProposalStatus = Literal[
    "PROPOSED",
    "AWAITING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "EXECUTING",
    "EXECUTED_UNVERIFIED",
    "VERIFIED_RESOLVED",
    "VERIFIED_UNRESOLVED",
    "EXECUTION_FAILED",
    "VERIFICATION_FAILED",
]


class ServiceSummary(BaseModel):
    name: str
    display_name: str
    status: str


class ServiceListResponse(BaseModel):
    services: list[ServiceSummary]
    mode: BundleMode
    warnings: list[str] = Field(default_factory=list)
    collected_at: datetime


class EvidenceItem(BaseModel):
    id: str
    category: str  # service_status | startup_type | event_log | service_list | os_info | ...
    source: str  # e.g. "powershell:Get-Service", "fixture:services", "tool:get_os_info:live"
    collected_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    # Rerun provenance (M007): which registered tool + validated args produced
    # this item. Absent for screenshots and pre-M007 legacy rows, which are
    # not re-runnable. refresh_of points at the older item a re-check
    # supersedes; the older item is always preserved, never replaced.
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    refresh_of: str | None = None


RefreshVerdict = Literal["changed", "unchanged", "unavailable"]


class EvidenceRefresh(BaseModel):
    """One historical-vs-current comparison. Both items stay in evidence."""

    old_evidence_id: str
    new_evidence_id: str | None = None  # None when the rerun failed entirely
    tool_name: str
    verdict: RefreshVerdict
    changes: list[str] = Field(default_factory=list)
    old_collected_at: datetime
    new_collected_at: datetime | None = None
    compared_at: datetime
    # Titles of hypotheses (causes) that cited the old item: they were built
    # on superseded readings and may need review.
    affected_causes: list[str] = Field(default_factory=list)


class Contradiction(BaseModel):
    """An apparent conflict between observations (deterministic rule hit)."""

    contradiction_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    description: str


class RecheckSuggestion(BaseModel):
    """One targeted re-check recommendation with its supporting evidence."""

    evidence_id: str
    tool_name: str
    reason: str


class DiagnosticBundle(BaseModel):
    service_name: str
    display_name: str | None = None
    collected_at: datetime
    mode: BundleMode
    items: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ObservedFact(BaseModel):
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)


class RootCause(BaseModel):
    title: str
    description: str
    likelihood: Likelihood = "low"
    evidence_ids: list[str] = Field(default_factory=list)


class ProposedAction(BaseModel):
    action_id: str
    target: str
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


StepImpact = Literal["read-only", "changes-system", "unknown"]


class RunbookStep(BaseModel):
    """One evidence-linked manual next step (INFERRED guidance, not fact)."""

    step: str
    why: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    inspect: str = ""
    confirms: str = ""
    impact: StepImpact = "unknown"
    admin_maybe: bool = False


class AnalysisResult(BaseModel):
    summary: str
    facts: list[ObservedFact] = Field(default_factory=list)
    causes: list[RootCause] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    next_steps: list[RunbookStep] = Field(default_factory=list)
    explanation: str
    mode: AnalysisMode
    model: str
    validation_warnings: list[str] = Field(default_factory=list)
    proposed_action: ProposedAction | None = None


class IncidentAssessment(BaseModel):
    incident_id: str
    service_name: str
    created_at: datetime
    diagnostics: DiagnosticBundle
    analysis: AnalysisResult
    warnings: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    service_name: str
    use_fixtures: bool | None = None


class StatusResponse(BaseModel):
    service: str = "fieldrook-api"
    version: str = "0.1.0"
    platform: str
    live_diagnostics_available: bool
    model_mode: AnalysisMode
    model_name: str
    fixtures_available: bool = True


class ActivityRecord(BaseModel):
    seq: int
    kind: ActivityKind
    title: str
    detail: str = ""
    tool_name: str | None = None
    duration_ms: int | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationResponse(BaseModel):
    investigation_id: str
    problem: str
    service_name: str | None = None
    status: InvestigationStatus = "complete"
    created_at: datetime
    uses_fixtures: bool = False
    analysis_mode: AnalysisMode = "simulated"
    model: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    activity: list[ActivityRecord] = Field(default_factory=list)
    assessment: AnalysisResult | None = None
    warnings: list[str] = Field(default_factory=list)
    has_screenshot: bool = False
    proposals: list[ActionProposal] = Field(default_factory=list)
    executions: list[ActionExecution] = Field(default_factory=list)
    notes: list[TechnicianNote] = Field(default_factory=list)
    refreshes: list[EvidenceRefresh] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    suggested_rechecks: list[RecheckSuggestion] = Field(default_factory=list)
    tool_calls_used: int = 0
    tool_calls_max: int = 12


class TechnicianNote(BaseModel):
    note_id: str
    text: str
    created_at: datetime


class FollowupRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class NoteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ReverifyRequest(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=32)


class ActionProposal(BaseModel):
    proposal_id: str
    investigation_id: str
    action_id: str
    target: str
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    risk: str = "low"
    action_description: str = ""
    expected_result: str = ""
    verification_method: str = ""
    status: ActionProposalStatus = "PROPOSED"
    created_at: datetime
    decided_at: datetime | None = None
    decision: str | None = None
    approval_token_hash: str | None = None
    approval_expires_at: float | None = None
    approval_used: bool = False
    approval_args_hash: str | None = None
    approval_digest: str | None = None


class ActionExecution(BaseModel):
    execution_id: str
    proposal_id: str
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    outcome: str = ""
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class InvestigationSummary(BaseModel):
    investigation_id: str
    problem: str
    status: InvestigationStatus
    analysis_mode: AnalysisMode
    model: str
    created_at: str
    updated_at: str
    evidence_count: int = 0
    proposal_count: int = 0
    latest_outcome: str | None = None


class ToolInfo(BaseModel):
    name: str
    description: str
    category: str
