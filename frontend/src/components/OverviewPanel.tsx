import type { InvestigationResponse } from "../types";
import { EvidenceChip } from "./EvidenceChip";
import { resolutionOf } from "./WorkflowStage";

export type InvestigationView = "findings" | "evidence" | "resolve";

export interface NextAction {
  label: string;
  view: InvestigationView;
  focusId?: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  service_status: "Services",
  startup_type: "Services",
  service_details: "Services",
  service_list: "Services",
  event_log: "Event logs",
  app_crashes: "Applications",
  process_info: "Processes",
  os_info: "System",
  net_adapters: "Network",
  ip_config: "Network",
  dns_config: "Network",
  dns_test: "Network",
  connections: "Network",
  scheduled_tasks: "Scheduled tasks",
  demo_worker: "Demo worker",
  error_code: "Error codes",
  screenshot: "Screenshot",
};

/** One obvious next action, derived from the real lifecycle state. */
export function nextActionFor(inv: InvestigationResponse): NextAction {
  if (inv.proposals.some((p) => p.status === "AWAITING_APPROVAL")) {
    return { label: "Review proposed correction", view: "resolve" };
  }
  const plan = inv.plans.length > 0 ? inv.plans[inv.plans.length - 1] : null;
  if (plan?.status === "DRAFT") {
    return { label: "Capture pre-fix baseline", view: "resolve" };
  }
  if (plan?.status === "BASELINED") {
    return { label: "Record the intervention", view: "resolve" };
  }
  if (plan?.status === "INTERVENED") {
    return { label: "Confirm Fix", view: "resolve" };
  }
  if (plan?.status === "NOT_RESOLVED" || plan?.status === "INCONCLUSIVE") {
    return { label: "Continue investigation", view: "findings", focusId: "followup-input" };
  }
  const budgetLeft = inv.tool_calls_max - inv.tool_calls_used;
  if (inv.suggested_rechecks.length > 0 && budgetLeft > 0) {
    return { label: "Re-check stale evidence", view: "findings" };
  }
  const lastExecution =
    inv.executions.length > 0 ? inv.executions[inv.executions.length - 1] : null;
  if (lastExecution?.outcome === "VERIFIED_RESOLVED" || plan?.status === "VERIFIED_RESOLVED") {
    return { label: "Export report", view: "resolve" };
  }
  if (inv.proposals.length > 0 || inv.plans.length > 0 || inv.executions.length > 0) {
    return { label: "Review resolution", view: "resolve" };
  }
  return { label: "Continue investigation", view: "findings", focusId: "followup-input" };
}

export function OverviewPanel({
  investigation,
  onEvidenceClick,
  onOpenEvidence,
  onAction,
}: {
  investigation: InvestigationResponse;
  onEvidenceClick?: (id: string) => void;
  onOpenEvidence?: () => void;
  onAction?: (action: NextAction) => void;
}) {
  const usable = investigation.evidence.filter((e) => !e.error);
  const failed = investigation.evidence.filter((e) => e.error);
  const groups = new Map<string, number>();
  for (const item of usable) {
    const label = CATEGORY_LABELS[item.category] ?? item.category;
    groups.set(label, (groups.get(label) ?? 0) + 1);
  }
  const lead = investigation.assessment?.causes[0] ?? null;
  const resolution = resolutionOf(investigation);
  const action = nextActionFor(investigation);
  const toneClass =
    resolution.tone === "good"
      ? "result-good"
      : resolution.tone === "bad"
        ? "result-bad"
        : resolution.tone === "warn"
          ? "result-warn"
          : "";
  const openCount =
    (investigation.assessment?.uncertainties.length ?? 0) +
    (investigation.assessment?.missing_evidence.length ?? 0);

  return (
    <section className={`card overview result ${toneClass}`}>
      <div className="card-head">
        <h2>Incident overview</h2>
        <div className="badges">
          <span
            className={investigation.uses_fixtures ? "badge badge-sim" : "badge badge-live"}
            title={
              investigation.uses_fixtures
                ? "Evidence source for THIS investigation: synthetic fixtures"
                : "Evidence source for THIS investigation: live read-only diagnostics"
            }
          >
            {investigation.uses_fixtures ? "FIXTURES" : "LIVE DIAGNOSTICS"}
          </span>
          <span
            className={
              investigation.analysis_mode === "live" ? "badge badge-live" : "badge badge-sim"
            }
            title={
              investigation.analysis_mode === "live"
                ? "Reasoning engine for THIS investigation: live model"
                : "Reasoning engine for THIS investigation: simulated analysis"
            }
          >
            {investigation.analysis_mode === "live" ? "LIVE MODEL" : "SIMULATED"}
          </span>
          {investigation.has_screenshot && <span className="badge">SCREENSHOT</span>}
        </div>
      </div>
      {investigation.service_name && (
        <p className="muted">Suspected service: {investigation.service_name}</p>
      )}
      <p className="result-status">{resolution.label}</p>
      <p className="result-finding">
        <span className="runbook-label">Leading hypothesis — </span>
        {lead ? lead.title : <span className="muted">No hypothesis recorded yet.</span>}
      </p>
      {lead && (
        <div className="result-refs">
          <span className="likelihood">{lead.likelihood}</span>
          {lead.evidence_ids.map((eid) => (
            <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
          ))}
        </div>
      )}
      <p className="result-context">
        {usable.length} usable evidence item{usable.length === 1 ? "" : "s"}
        {failed.length > 0 && ` · ${failed.length} failed collection${failed.length === 1 ? "" : "s"}`}
        {openCount > 0 && ` · ${openCount} open uncertaint${openCount === 1 ? "y" : "ies"}`}
        {investigation.contradictions.length > 0 &&
          ` · ${investigation.contradictions.length} contradiction${investigation.contradictions.length === 1 ? "" : "s"}`}
        .
      </p>
      <div className="result-context">
        {[...groups.entries()].map(([label, count]) => (
          <button
            key={label}
            type="button"
            className="coverage"
            onClick={() => onOpenEvidence?.()}
            title="Open the Evidence view"
          >
            <strong>{label}</strong> ({count})
          </button>
        ))}
        {failed.length > 0 && (
          <span className="coverage coverage-failed">
            {failed.length} failed collection{failed.length === 1 ? "" : "s"}
          </span>
        )}
      </div>
      {investigation.warnings.map((w, i) => (
        <p key={i} className="warn">
          {w}
        </p>
      ))}
      {onAction && (
        <div className="result-next">
          <span className="result-next-label">Next step</span>
          <button type="button" className="button" onClick={() => onAction(action)}>
            {action.label}
          </button>
        </div>
      )}
    </section>
  );
}
