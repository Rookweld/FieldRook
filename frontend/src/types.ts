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
}

export interface ToolInfo {
  name: string;
  description: string;
  category: string;
}
