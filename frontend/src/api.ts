import type {
  DiagnosticBundle,
  DiagnosisTarget,
  IncidentAssessment,
  InvestigationResponse,
  InvestigationSummary,
  KnowledgeEntry,
  KnowledgeMatch,
  PlanTemplate,
  ProviderOption,
  LocalTestResult,
  ServiceListResponse,
  StatusResponse,
  ToolInfo,
  TurnKind,
} from "./types";
import type { ReferenceCitation, ReferencePassage } from "./forge/types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch (e) {
    throw new ApiError(0, e instanceof Error ? `Network error: ${e.message}` : "Network error");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// Guard the boundary between hot-reloaded frontend code and a still-running
// older backend process. A schema mismatch must show an actionable error,
// never crash React while rendering an incomplete investigation.
function requestInvestigation(path: string, init?: RequestInit): Promise<InvestigationResponse> {
  return request<InvestigationResponse>(path, init).then((inv) => {
    const arrays: (keyof InvestigationResponse)[] = [
      "evidence", "activity", "warnings", "proposals", "executions",
      "notes", "refreshes", "plans", "regression_checks",
      "contradictions", "suggested_rechecks",
      "hypotheses", "questions",
    ];
    if (!inv || arrays.some((field) => !Array.isArray(inv[field]))) {
      throw new ApiError(
        0,
        "FieldRook frontend/backend version mismatch. Restart the backend on port 8000 to load the current code, then try again. Existing investigations are preserved.",
      );
    }
    return inv;
  });
}

function fixturesQuery(useFixtures?: boolean): string {
  if (useFixtures === undefined) return "";
  return `?use_fixtures=${useFixtures ? "true" : "false"}`;
}

export function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/api/status");
}

export function listServices(useFixtures?: boolean): Promise<ServiceListResponse> {
  return request<ServiceListResponse>(`/api/services${fixturesQuery(useFixtures)}`);
}

export function getDiagnostics(
  name: string,
  useFixtures?: boolean,
): Promise<DiagnosticBundle> {
  return request<DiagnosticBundle>(
    `/api/services/${encodeURIComponent(name)}/diagnostics${fixturesQuery(useFixtures)}`,
  );
}

export function analyzeIncident(
  name: string,
  useFixtures?: boolean,
): Promise<IncidentAssessment> {
  return request<IncidentAssessment>("/api/incidents/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ service_name: name, use_fixtures: useFixtures ?? null }),
  });
}

export interface StartInvestigationArgs {
  problem: string;
  serviceName?: string;
  useFixtures?: boolean;
  shareConsent: boolean;
  screenshot?: File | null;
  target?: DiagnosisTarget;
  provider?: string;
}

export function startInvestigation(args: StartInvestigationArgs): Promise<InvestigationResponse> {
  const form = new FormData();
  form.append("problem", args.problem);
  if (args.serviceName) form.append("service_name", args.serviceName);
  if (args.useFixtures !== undefined) form.append("use_fixtures", args.useFixtures ? "true" : "false");
  form.append("share_consent", args.shareConsent ? "true" : "false");
  if (args.screenshot) form.append("screenshot", args.screenshot, args.screenshot.name);
  if (args.target) form.append("target", args.target);
  if (args.provider) form.append("provider", args.provider);
  return requestInvestigation("/api/investigations", {
    method: "POST",
    body: form,
  });
}

export interface TurnArgs {
  kind: TurnKind;
  text: string;
  questionId?: string | null;
  shareConsent: boolean;
  screenshot?: File | null;
}

export function sendTurn(id: string, args: TurnArgs): Promise<InvestigationResponse> {
  const form = new FormData();
  form.append("kind", args.kind);
  form.append("text", args.text);
  if (args.questionId) form.append("question_id", args.questionId);
  form.append("share_consent", args.shareConsent ? "true" : "false");
  if (args.screenshot) form.append("screenshot", args.screenshot, args.screenshot.name);
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/turn`,
    { method: "POST", body: form },
  );
}

export function completePlanStep(
  id: string,
  stepId: string,
  outcome: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/plan/steps/${encodeURIComponent(stepId)}/complete`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome }),
    },
  );
}

export function impossiblePlanStep(
  id: string,
  stepId: string,
  reason: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/plan/steps/${encodeURIComponent(stepId)}/impossible`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    },
  );
}

export function setHypothesisStatus(
  id: string,
  hypothesisId: string,
  status: string,
  reason: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/hypotheses/${encodeURIComponent(hypothesisId)}/status`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, reason }),
    },
  );
}

export function switchProvider(
  id: string,
  provider: string,
  confirmCloud: boolean,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/provider`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, confirm_cloud: confirmCloud }),
    },
  );
}

export function setTarget(
  id: string,
  target: DiagnosisTarget,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/target`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    },
  );
}

export function listProviders(): Promise<ProviderOption[]> {
  return request<ProviderOption[]>("/api/providers");
}

export function testLocalProvider(): Promise<LocalTestResult> {
  return request<LocalTestResult>("/api/providers/local/test", { method: "POST" });
}

export function cancelRound(id: string): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/cancel`,
    { method: "POST" },
  );
}

export function followUpInvestigation(
  id: string,
  message: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/followup`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    },
  );
}

export function addInvestigationNote(
  id: string,
  text: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/notes`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
  );
}

export function reverifyEvidence(
  id: string,
  evidenceId: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/reverify`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ evidence_id: evidenceId }),
    },
  );
}

export interface CriterionDraft {
  description: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  path: string;
  op: string;
  expected: unknown;
}

export interface PlanCreateArgs {
  investigationId: string;
  evidence_ids: string[];
  intended_state: string;
  criteria: CriterionDraft[];
  guidance: string;
  risks: string;
  remediation_kind: "manual" | "action";
  action_id?: string;
  target?: string;
}

export function getPlanTemplate(actionId: string): Promise<PlanTemplate> {
  return request<PlanTemplate>(`/api/plans/template?action_id=${encodeURIComponent(actionId)}`);
}

export function createPlan(args: PlanCreateArgs): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(args.investigationId)}/plans`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        evidence_ids: args.evidence_ids,
        intended_state: args.intended_state,
        criteria: args.criteria,
        guidance: args.guidance,
        risks: args.risks,
        remediation_kind: args.remediation_kind,
        action_id: args.action_id ?? null,
        target: args.target ?? null,
      }),
    },
  );
}

export function captureBaseline(planId: string): Promise<InvestigationResponse> {
  return requestInvestigation(`/api/plans/${encodeURIComponent(planId)}/baseline`, {
    method: "POST",
  });
}

export function recordManualIntervention(
  planId: string,
  description: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/plans/${encodeURIComponent(planId)}/interventions/manual`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    },
  );
}

export function linkPlanExecution(
  planId: string,
  executionId: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/plans/${encodeURIComponent(planId)}/interventions/link-execution`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ execution_id: executionId }),
    },
  );
}

export function verifyPlan(planId: string): Promise<InvestigationResponse> {
  return requestInvestigation(`/api/plans/${encodeURIComponent(planId)}/verify`, {
    method: "POST",
  });
}

export function recordKnowledge(
  investigationId: string,
  confirmedCause: string,
): Promise<KnowledgeEntry> {
  return request<KnowledgeEntry>(
    `/api/investigations/${encodeURIComponent(investigationId)}/knowledge`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed_cause: confirmedCause }),
    },
  );
}

export function listKnowledge(params: {
  q?: string;
  category?: string;
  outcome?: string;
} = {}): Promise<KnowledgeEntry[]> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.category) search.set("category", params.category);
  if (params.outcome) search.set("outcome", params.outcome);
  const suffix = search.toString();
  return request<KnowledgeEntry[]>(`/api/knowledge${suffix ? `?${suffix}` : ""}`);
}

export function getKnowledgeEntry(entryId: string): Promise<KnowledgeEntry> {
  return request<KnowledgeEntry>(`/api/knowledge/${encodeURIComponent(entryId)}`);
}

export function deleteKnowledgeEntry(entryId: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/api/knowledge/${encodeURIComponent(entryId)}`, {
    method: "DELETE",
  });
}

export function knowledgeExportUrl(entryId: string, format: "markdown" | "json"): string {
  return `/api/knowledge/${encodeURIComponent(entryId)}/export?format=${format}`;
}

export function fetchKnowledgeMatches(
  investigationId: string,
  limit = 5,
): Promise<{ matches: KnowledgeMatch[] }> {
  return request<{ matches: KnowledgeMatch[] }>(
    `/api/investigations/${encodeURIComponent(investigationId)}/knowledge/matches?limit=${limit}`,
  );
}

export interface ReferenceBundle {
  passages: ReferencePassage[];
  citations: ReferenceCitation[];
  message: string;
}

export function fetchReferencePassages(
  investigationId: string,
  limit = 5,
): Promise<ReferenceBundle> {
  return request<ReferenceBundle>(
    `/api/investigations/${encodeURIComponent(investigationId)}/knowledge/references?limit=${limit}`,
  );
}

export function uploadCollectorPackage(
  id: string,
  form: FormData,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}/import-collector`,
    { method: "POST", body: form },
  );
}

export function recheckKnowledgeEntry(
  investigationId: string,
  entryId: string,
): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(investigationId)}/knowledge/${encodeURIComponent(entryId)}/recheck`,
    { method: "POST" },
  );
}

export function listTools(): Promise<ToolInfo[]> {
  return request<ToolInfo[]>("/api/tools");
}

export function getInvestigation(id: string): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(id)}`,
  );
}

export function listInvestigations(limit = 50): Promise<InvestigationSummary[]> {
  return request<InvestigationSummary[]>(`/api/investigations?limit=${limit}`);
}

export interface ProposeActionArgs {
  investigationId: string;
  actionId: string;
  target: string;
  reason: string;
}

export function proposeAction(args: ProposeActionArgs): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/investigations/${encodeURIComponent(args.investigationId)}/proposals`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_id: args.actionId,
        target: args.target,
        reason: args.reason,
      }),
    },
  );
}

export interface ApproveResult {
  investigation: InvestigationResponse;
  approval_token: string;
  expires_in_s: number;
}

export function approveProposal(proposalId: string): Promise<ApproveResult> {
  return request<ApproveResult>(`/api/proposals/${encodeURIComponent(proposalId)}/approve`, {
    method: "POST",
  });
}

export interface ExecuteResult {
  investigation: InvestigationResponse;
  execution_id: string;
  outcome: string;
}

export function rejectProposal(proposalId: string): Promise<InvestigationResponse> {
  return requestInvestigation(
    `/api/proposals/${encodeURIComponent(proposalId)}/reject`,
    { method: "POST" },
  );
}

export function executeProposal(
  proposalId: string,
  approvalToken: string,
): Promise<ExecuteResult> {
  return request<ExecuteResult>(
    `/api/proposals/${encodeURIComponent(proposalId)}/execute`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approval_token: approvalToken, args: {} }),
    },
  );
}

/* ------------------------------------------------------------------ */
/* M026 GAMMA extensions (append-only). No existing signature above is  */
/* modified: every export below is NEW. Views built by BETA consume     */
/* these through frontend/src/signalforge/hooks/**.                    */
/* ------------------------------------------------------------------ */

export type ExportFormat = "markdown" | "json";

/** Status plus the M025 Z1 desktop-identity field the backend returns. */
export type DesktopStatusResponse = StatusResponse & { runtime: string };

export function getDesktopStatus(): Promise<DesktopStatusResponse> {
  return request<DesktopStatusResponse>("/api/status");
}

export function investigationExportUrl(id: string, format: ExportFormat): string {
  return `/api/investigations/${encodeURIComponent(id)}/export?format=${format}`;
}

async function requestText(path: string, init?: RequestInit): Promise<string> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch (e) {
    throw new ApiError(0, e instanceof Error ? `Network error: ${e.message}` : "Network error");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* error body is not JSON; keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.text();
}

/** Fetch the report body as text (for the desktop save dialog path). */
export function fetchInvestigationExport(id: string, format: ExportFormat): Promise<string> {
  return requestText(investigationExportUrl(id, format));
}

/** Fetch a knowledge entry export as text (for the desktop save path). */
export function fetchKnowledgeExport(
  entryId: string,
  format: ExportFormat,
): Promise<string> {
  return requestText(knowledgeExportUrl(entryId, format));
}
