import type {
  DiagnosticBundle,
  IncidentAssessment,
  InvestigationResponse,
  InvestigationSummary,
  ServiceListResponse,
  StatusResponse,
  ToolInfo,
} from "./types";

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
}

export function startInvestigation(args: StartInvestigationArgs): Promise<InvestigationResponse> {
  const form = new FormData();
  form.append("problem", args.problem);
  if (args.serviceName) form.append("service_name", args.serviceName);
  if (args.useFixtures !== undefined) form.append("use_fixtures", args.useFixtures ? "true" : "false");
  form.append("share_consent", args.shareConsent ? "true" : "false");
  if (args.screenshot) form.append("screenshot", args.screenshot, args.screenshot.name);
  return request<InvestigationResponse>("/api/investigations", {
    method: "POST",
    body: form,
  });
}

export function followUpInvestigation(
  id: string,
  message: string,
): Promise<InvestigationResponse> {
  return request<InvestigationResponse>(
    `/api/investigations/${encodeURIComponent(id)}/followup`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    },
  );
}

export function listTools(): Promise<ToolInfo[]> {
  return request<ToolInfo[]>("/api/tools");
}

export function getInvestigation(id: string): Promise<InvestigationResponse> {
  return request<InvestigationResponse>(
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
  return request<InvestigationResponse>(
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
  return request<InvestigationResponse>(
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
