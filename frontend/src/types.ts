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

export interface AnalysisResult {
  summary: string;
  facts: ObservedFact[];
  causes: RootCause[];
  uncertainties: string[];
  missing_evidence: string[];
  next_actions: string[];
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
  action_id: string;
  target: string;
  started_at: string;
  finished_at: string | null;
  outcome: ProposalStatus;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  verified: boolean;
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
