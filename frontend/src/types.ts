export interface ServiceSummary {
  name: string;
  display_name: string;
  status: string;
}

export interface ServiceListResponse {
  services: ServiceSummary[];
  mode: "live" | "fixture";
  warnings: string[];
  collected_at: string;
}

export interface EvidenceItem {
  id: string;
  category: string;
  source: string;
  collected_at: string;
  data: Record<string, unknown>;
  error: string | null;
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
  refresh_of: string | null;
}

export type RefreshVerdict = "changed" | "unchanged" | "unavailable";

export interface EvidenceRefresh {
  old_evidence_id: string;
  new_evidence_id: string | null;
  tool_name: string;
  verdict: RefreshVerdict;
  changes: string[];
  old_collected_at: string;
  new_collected_at: string | null;
  compared_at: string;
  affected_causes: string[];
}

export interface Contradiction {
  contradiction_id: string;
  evidence_ids: string[];
  description: string;
}

export type KnowledgeOutcome = "VERIFIED_RESOLVED" | "NOT_RESOLVED" | "INCONCLUSIVE" | "UNRESOLVED";
export type RecheckOutcome = "CONFIRMED" | "REGRESSION" | "INCONCLUSIVE";

export interface KnowledgeLink {
  investigation_id: string;
  plan_id: string | null;
  outcome: KnowledgeOutcome;
  recorded_at: string;
}

export interface KnowledgeEntry {
  entry_id: string;
  cluster_key: string;
  source_investigation_id: string;
  source_plan_id: string | null;
  problem: string;
  category: string;
  symptoms: string[];
  identity: string | null;
  event_codes: string[];
  evidence_signature: Record<string, string>;
  root_cause: string | null;
  root_cause_verified: boolean;
  intervention: string;
  intervention_kind: string;
  criteria: ResolutionCriterion[];
  baseline_values: Record<string, unknown>;
  verified_values: Record<string, unknown>;
  outcome: KnowledgeOutcome;
  verified_at: string | null;
  created_at: string;
  source_evidence_ids: string[];
  occurrence_count: number;
  investigations: KnowledgeLink[];
}

export interface MatchSignal {
  signal: string;
  detail: string;
  weight: number;
}

export interface KnowledgeMatch {
  entry: KnowledgeEntry;
  strength: number;
  signals: MatchSignal[];
  differences: string[];
  missing_evidence: string[];
}

export interface RegressionCheck {
  check_id: string;
  entry_id: string;
  investigation_id: string;
  checked_at: string;
  outcome: RecheckOutcome;
  results: CriterionResult[];
  uncertainties: string[];
  evidence_ids: string[];
}

export type CriterionOp = "eq" | "ne" | "contains" | "gt" | "gte" | "lt" | "lte" | "exists";

export interface ResolutionCriterion {
  criterion_id: string;
  description: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  path: string;
  op: CriterionOp;
  expected: unknown;
}

export type InterventionKind = "manual" | "action";

export interface PlanIntervention {
  kind: InterventionKind;
  description: string;
  proposal_id: string | null;
  execution_id: string | null;
  recorded_at: string;
}

export type CriterionOutcome = "pass" | "fail" | "inconclusive";

export interface CriterionResult {
  criterion_id: string;
  outcome: CriterionOutcome;
  observed: unknown;
  before_evidence_id: string | null;
  after_evidence_id: string | null;
  detail: string;
}

export type PlanOutcome = "VERIFIED_RESOLVED" | "NOT_RESOLVED" | "INCONCLUSIVE";

export interface PlanVerification {
  verification_id: string;
  verified_at: string;
  after_evidence_ids: string[];
  results: CriterionResult[];
  outcome: PlanOutcome;
  uncertainties: string[];
}

export type PlanStatus =
  | "DRAFT"
  | "BASELINED"
  | "INTERVENED"
  | PlanOutcome;

export interface ResolutionPlan {
  plan_id: string;
  investigation_id: string;
  problem: string;
  evidence_ids: string[];
  intended_state: string;
  criteria: ResolutionCriterion[];
  guidance: string;
  risks: string;
  remediation_kind: InterventionKind;
  action_id: string | null;
  target: string | null;
  interventions: PlanIntervention[];
  baseline_evidence_ids: string[];
  baseline_captured_at: string | null;
  baseline_values: Record<string, unknown>;
  verifications: PlanVerification[];
  status: PlanStatus;
  created_at: string;
}

export interface PlanTemplate {
  action_id: string;
  target: string;
  intended_state: string;
  guidance: string;
  risks: string;
  criteria: Array<{
    description: string;
    tool_name: string;
    tool_args: Record<string, unknown>;
    path: string;
    op: CriterionOp;
    expected: unknown;
  }>;
}

export interface RecheckSuggestion {
  evidence_id: string;
  tool_name: string;
  reason: string;
}

export interface DiagnosticBundle {
  service_name: string;
  display_name: string | null;
  collected_at: string;
  mode: "live" | "fixture";
  items: EvidenceItem[];
  warnings: string[];
}

export interface ObservedFact {
  statement: string;
  evidence_ids: string[];
}

export interface RootCause {
  title: string;
  description: string;
  likelihood: "high" | "medium" | "low";
  evidence_ids: string[];
}

export type StepImpact = "read-only" | "changes-system" | "unknown";

export interface RunbookStep {
  step: string;
  why: string;
  evidence_ids: string[];
  inspect: string;
  confirms: string;
  impact: StepImpact;
  admin_maybe: boolean;
}

export interface TechnicianNote {
  note_id: string;
  text: string;
  created_at: string;
}

export interface AnalysisResult {
  summary: string;
  facts: ObservedFact[];
  causes: RootCause[];
  uncertainties: string[];
  missing_evidence: string[];
  next_actions: string[];
  next_steps: RunbookStep[];
  explanation: string;
  mode: "live" | "simulated";
  model: string;
  validation_warnings: string[];
}

export interface IncidentAssessment {
  incident_id: string;
  service_name: string;
  created_at: string;
  diagnostics: DiagnosticBundle;
  analysis: AnalysisResult;
  warnings: string[];
}

export interface StatusResponse {
  service: string;
  version: string;
  platform: string;
  live_diagnostics_available: boolean;
  model_mode: "live" | "simulated";
  model_name: string;
  fixtures_available: boolean;
}

export type ActivityKind =
  | "plan"
  | "tool_request"
  | "tool_result"
  | "evidence"
  | "note"
  | "reverify"
  | "proposed"
  | "approval_requested"
  | "approved"
  | "rejected"
  | "executed"
  | "verification_started"
  | "verified"
  | "done"
  | "error";

export interface ActivityRecord {
  seq: number;
  kind: ActivityKind;
  title: string;
  detail: string;
  tool_name: string | null;
  duration_ms: number | null;
  evidence_ids: string[];
}

export type ProposalStatus =
  | "PROPOSED"
  | "AWAITING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "EXECUTING"
  | "EXECUTED_UNVERIFIED"
  | "VERIFIED_RESOLVED"
  | "VERIFIED_UNRESOLVED"
  | "EXECUTION_FAILED"
  | "VERIFICATION_FAILED";

export interface ActionProposal {
  proposal_id: string;
  action_id: string;
  target: string;
  args: Record<string, unknown>;
  reason: string;
  evidence_ids: string[];
  status: ProposalStatus;
  risk: string;
  expected_result: string;
  verification: string;
  created_at: string;
  decision: string | null;
  decided_at: string | null;
}

export interface ActionExecution {
  execution_id: string;
  proposal_id: string;
  // Optional: the backend identifies the action via the linked proposal.
  action_id?: string;
  target?: string;
  started_at: string;
  finished_at: string | null;
  outcome: ProposalStatus;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  // Optional: the backend encodes verification in `outcome` (VERIFIED_*).
  verified?: boolean;
  error: string | null;
}

export interface InvestigationResponse {
  investigation_id: string;
  problem: string;
  service_name: string | null;
  status: "complete" | "partial" | "error";
  created_at: string;
  uses_fixtures: boolean;
  analysis_mode: "live" | "simulated";
  model: string;
  evidence: EvidenceItem[];
  activity: ActivityRecord[];
  assessment: AnalysisResult | null;
  warnings: string[];
  has_screenshot: boolean;
  proposals: ActionProposal[];
  executions: ActionExecution[];
  notes: TechnicianNote[];
  refreshes: EvidenceRefresh[];
  contradictions: Contradiction[];
  suggested_rechecks: RecheckSuggestion[];
  plans: ResolutionPlan[];
  regression_checks: RegressionCheck[];
  tool_calls_used: number;
  tool_calls_max: number;
}

export interface InvestigationSummary {
  investigation_id: string;
  problem: string;
  status: string;
  created_at: string;
  updated_at: string;
  evidence_count: number;
  proposal_count: number;
  latest_outcome: string | null;
}

export interface ToolInfo {
  name: string;
  description: string;
  category: string;
}
