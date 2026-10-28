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
    "hypothesis",
    "troubleshoot_plan",
    "turn",
    "question",
    "provider",
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
    # M016 adaptive layer (all optional; parsed leniently, never required).
    understanding: str = ""
    provider: str = ""
    suggested_hypotheses: list["SuggestedHypothesis"] = Field(default_factory=list)
    suggested_plan: "SuggestedPlan | None" = None
    suggested_questions: list["SuggestedQuestion"] = Field(default_factory=list)


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
    plans: list["ResolutionPlan"] = Field(default_factory=list)
    regression_checks: list["RegressionCheck"] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    suggested_rechecks: list[RecheckSuggestion] = Field(default_factory=list)
    tool_calls_used: int = 0
    tool_calls_max: int = 12
    # M016 adaptive layer (all defaulted for backward compatibility).
    stage: InvestigationStage = "INVESTIGATING"
    target: DiagnosisTarget = "local"
    understanding: str = ""
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    plan: TroubleshootPlan | None = None
    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    provider_info: ProviderInfo | None = None
    rounds_used: int = 0
    blocked_reason: str | None = None
    assistant_message: str = ""


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


CriterionOp = Literal["eq", "ne", "contains", "gt", "gte", "lt", "lte", "exists"]
PlanOutcome = Literal["VERIFIED_RESOLVED", "NOT_RESOLVED", "INCONCLUSIVE"]
PlanStatus = Literal[
    "DRAFT", "BASELINED", "INTERVENED",
    "VERIFIED_RESOLVED", "NOT_RESOLVED", "INCONCLUSIVE",
]
InterventionKind = Literal["manual", "action"]
CriterionOutcome = Literal["pass", "fail", "inconclusive"]


class ResolutionCriterion(BaseModel):
    """One measurable success check: tool + dot-path + comparison."""

    criterion_id: str
    description: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    path: str
    op: CriterionOp
    expected: Any = None


class PlanIntervention(BaseModel):
    """A recorded intervention. A manual record is a technician claim, never
    proof; an action record links a real authorized execution. Proof comes
    only from measured verification."""

    kind: InterventionKind
    description: str = ""
    proposal_id: str | None = None
    execution_id: str | None = None
    recorded_at: datetime


class CriterionResult(BaseModel):
    criterion_id: str
    outcome: CriterionOutcome
    observed: Any = None
    before_evidence_id: str | None = None
    after_evidence_id: str | None = None
    detail: str = ""


class PlanVerification(BaseModel):
    verification_id: str
    verified_at: datetime
    after_evidence_ids: list[str] = Field(default_factory=list)
    results: list[CriterionResult] = Field(default_factory=list)
    outcome: PlanOutcome
    uncertainties: list[str] = Field(default_factory=list)


class ResolutionPlan(BaseModel):
    plan_id: str
    investigation_id: str
    problem: str
    evidence_ids: list[str] = Field(default_factory=list)
    intended_state: str
    criteria: list[ResolutionCriterion] = Field(default_factory=list)
    guidance: str = ""
    risks: str = ""
    remediation_kind: InterventionKind = "manual"
    action_id: str | None = None
    target: str | None = None
    interventions: list[PlanIntervention] = Field(default_factory=list)
    baseline_evidence_ids: list[str] = Field(default_factory=list)
    baseline_captured_at: datetime | None = None
    baseline_values: dict[str, Any] = Field(default_factory=dict)
    verifications: list[PlanVerification] = Field(default_factory=list)
    status: PlanStatus = "DRAFT"
    created_at: datetime


KnowledgeOutcome = Literal["VERIFIED_RESOLVED", "NOT_RESOLVED", "INCONCLUSIVE", "UNRESOLVED"]
RecheckOutcome = Literal["CONFIRMED", "REGRESSION", "INCONCLUSIVE"]


class KnowledgeLink(BaseModel):
    investigation_id: str
    plan_id: str | None = None
    outcome: KnowledgeOutcome
    recorded_at: datetime


class KnowledgeEntry(BaseModel):
    """One remembered incident. Verified outcomes cite measured criteria;
    inferred causes stay labeled as hypotheses, never facts."""

    entry_id: str
    cluster_key: str
    source_investigation_id: str
    source_plan_id: str | None = None
    problem: str
    category: str
    symptoms: list[str] = Field(default_factory=list)
    identity: str | None = None
    event_codes: list[str] = Field(default_factory=list)
    evidence_signature: dict[str, Any] = Field(default_factory=dict)
    root_cause: str | None = None
    root_cause_verified: bool = False
    intervention: str = ""
    intervention_kind: str = "none"
    criteria: list["ResolutionCriterion"] = Field(default_factory=list)
    baseline_values: dict[str, Any] = Field(default_factory=dict)
    verified_values: dict[str, Any] = Field(default_factory=dict)
    outcome: KnowledgeOutcome = "UNRESOLVED"
    verified_at: datetime | None = None
    created_at: datetime
    source_evidence_ids: list[str] = Field(default_factory=list)
    occurrence_count: int = 1
    investigations: list[KnowledgeLink] = Field(default_factory=list)


class MatchSignal(BaseModel):
    signal: str
    detail: str
    weight: int


class KnowledgeMatch(BaseModel):
    entry: KnowledgeEntry
    strength: int
    signals: list[MatchSignal] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class RegressionCheck(BaseModel):
    check_id: str
    entry_id: str
    investigation_id: str
    checked_at: datetime
    outcome: RecheckOutcome
    results: list[CriterionResult] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# M016 adaptive investigation layer: lifecycle stage, diagnostic target,
# versioned hypotheses, dynamic troubleshooting plans, clarifying questions,
# technician turns, and provider selection. All model-suggested content is
# untrusted input: validated, evidence-checked, and merged by the assist
# engine, never applied blindly.
# ---------------------------------------------------------------------------

DiagnosisTarget = Literal["local", "remote", "unknown"]
InvestigationStage = Literal[
    "INTAKE",
    "CLARIFYING",
    "PLANNING",
    "INVESTIGATING",
    "REASSESSING",
    "READY_TO_RESOLVE",
    "VERIFYING",
    "RESOLVED",
    "BLOCKED",
]
HypothesisStatus = Literal["active", "weakened", "ruled_out", "confirmed"]
PlanStepKind = Literal[
    "AUTOMATED_READ_ONLY",
    "TECHNICIAN_CHECK",
    "CLARIFYING_QUESTION",
    "EXTERNAL_SYSTEM_CHECK",
    "PROPOSED_INTERVENTION",
    "VERIFICATION",
]
PlanStepStatus = Literal["suggested", "current", "done", "blocked", "skipped"]
QuestionStatus = Literal["open", "answered"]
TurnKind = Literal["answer", "observation", "test_result", "correction", "question"]
ProviderName = Literal["auto", "meta", "simulated", "local"]


class SuggestedHypothesis(BaseModel):
    """One model-proposed hypothesis (untrusted until merged by assist)."""

    title: str
    description: str = ""
    status: HypothesisStatus = "active"
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)


class SuggestedPlanStep(BaseModel):
    """One model-proposed troubleshooting step (untrusted until merged)."""

    instruction: str
    why: str = ""
    kind: PlanStepKind = "TECHNICIAN_CHECK"
    tool_name: str | None = None
    expected_observations: list[str] = Field(default_factory=list)
    admin_maybe: bool = False


class SuggestedPlan(BaseModel):
    steps: list[SuggestedPlanStep] = Field(default_factory=list)


class SuggestedQuestion(BaseModel):
    """One model-proposed clarifying question (untrusted until merged)."""

    question: str
    why: str = ""


class HypothesisEvent(BaseModel):
    """One status transition. History is append-only; nothing is rewritten."""

    round: int = 0
    status: HypothesisStatus = "active"
    reason: str = ""


class Hypothesis(BaseModel):
    hypothesis_id: str
    title: str
    description: str = ""
    status: HypothesisStatus = "active"
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    created_round: int = 0
    updated_round: int = 0
    history: list[HypothesisEvent] = Field(default_factory=list)


class TroubleshootStep(BaseModel):
    step_id: str
    instruction: str
    why: str = ""
    kind: PlanStepKind = "TECHNICIAN_CHECK"
    status: PlanStepStatus = "suggested"
    tool_name: str | None = None
    expected_observations: list[str] = Field(default_factory=list)
    outcome: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    admin_maybe: bool = False


class TroubleshootPlan(BaseModel):
    plan_id: str
    updated_round: int = 0
    steps: list[TroubleshootStep] = Field(default_factory=list)
    current_step_id: str | None = None


class ClarifyingQuestion(BaseModel):
    question_id: str
    question: str
    why: str = ""
    status: QuestionStatus = "open"
    answer: str = ""


class ProviderInfo(BaseModel):
    name: str = "simulated"
    model: str = ""
    processing_location: str = "none"  # "cloud" | "local" | "none"
    vision: bool = False
    tool_calling: bool = False


class TurnRequest(BaseModel):
    kind: TurnKind = "observation"
    text: str = Field(min_length=1, max_length=2000)
    question_id: str | None = None


class PlanStepOutcomeRequest(BaseModel):
    outcome: str = Field(min_length=1, max_length=2000)


class PlanStepImpossibleRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class HypothesisStatusRequest(BaseModel):
    status: HypothesisStatus
    reason: str = Field(min_length=1, max_length=1000)


class ProviderSwitchRequest(BaseModel):
    provider: Literal["auto", "meta", "simulated", "local"] = "simulated"
    # Required when switching TO a cloud provider while the investigation
    # holds screenshots, evidence, or notes: that content would be sent to
    # the cloud model on the next round.
    confirm_cloud: bool = False


class TargetRequest(BaseModel):
    target: DiagnosisTarget = "local"


# (Forward references resolved at the end of this module.)


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


# ResolutionPlan and ActionProposal are defined after InvestigationResponse;
# resolve those forward references now that the module is complete.
InvestigationResponse.model_rebuild()
AnalysisResult.model_rebuild()
