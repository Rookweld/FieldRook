import type { InvestigationResponse } from "../types";
import { EvidenceChip } from "./EvidenceChip";

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

export function OverviewPanel({
  investigation,
  onEvidenceClick,
}: {
  investigation: InvestigationResponse;
  onEvidenceClick?: (id: string) => void;
}) {
  const usable = investigation.evidence.filter((e) => !e.error);
  const failed = investigation.evidence.filter((e) => e.error);
  const groups = new Map<string, string[]>();
  for (const item of usable) {
    const label = CATEGORY_LABELS[item.category] ?? item.category;
    const ids = groups.get(label) ?? [];
    ids.push(item.id);
    groups.set(label, ids);
  }
  const lead = investigation.assessment?.causes[0] ?? null;
  const steps = investigation.assessment?.next_steps ?? [];
  const topStep =
    steps[0]?.step ?? investigation.assessment?.next_actions[0] ?? null;

  return (
    <section className="card overview">
      <div className="card-head">
        <h2>Incident overview</h2>
        <span className="muted">
          {usable.length} usable &middot; {failed.length} failed
        </span>
      </div>
      <dl className="overview-grid">
        <div>
          <dt>Leading hypothesis</dt>
          <dd>
            {lead ? (
              <>
                <span className="tag tag-inf">INFERRED</span> <strong>{lead.title}</strong>{" "}
                <span className="likelihood">{lead.likelihood}</span>{" "}
                {lead.evidence_ids.map((eid) => (
                  <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
                ))}
              </>
            ) : (
              <span className="muted">No hypothesis recorded yet.</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Evidence coverage</dt>
          <dd>
            {groups.size === 0 && <span className="muted">No evidence collected.</span>}
            {[...groups.entries()].map(([label, ids]) => (
              <span key={label} className="coverage">
                <strong>{label}</strong> ({ids.length})
              </span>
            ))}
            {failed.length > 0 && (
              <span className="coverage coverage-failed">
                {failed.length} failed collection{failed.length === 1 ? "" : "s"}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>Most useful next step</dt>
          <dd>
            {topStep ? (
              <span>{topStep}</span>
            ) : (
              <span className="muted">No guidance recorded.</span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}
