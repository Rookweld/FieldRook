import type {
  DiagnosticBundle,
  IncidentAssessment,
  ServiceListResponse,
  StatusResponse,
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
