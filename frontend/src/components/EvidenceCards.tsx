import { useEffect } from "react";
import type { EvidenceItem, EvidenceRefresh } from "../types";

const PREVIEW_CHARS = 500;

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

// M011: tool warnings (truncation, fixture fallback) live in data.warnings;
// they are material to trust, so the card surfaces them above the JSON.
function dataWarnings(item: EvidenceItem): string[] {
  const w: unknown = item.data["warnings"];
  if (!Array.isArray(w)) return [];
  return w.filter((x): x is string => typeof x === "string");
}

function previewText(item: EvidenceItem): string {
  const pretty = JSON.stringify(item.data, null, 2);
  if (pretty.length <= PREVIEW_CHARS) return pretty;
  return `${pretty.slice(0, PREVIEW_CHARS)}\n\u2026 (+${pretty.length - PREVIEW_CHARS} chars, see full JSON)`;
}

export function EvidenceCards({
  evidence,
  selectedId,
  onSelect,
  refreshes,
  onReverify,
  reverifyingId,
  reverifyDisabled,
}: {
  evidence: EvidenceItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  refreshes?: EvidenceRefresh[];
  onReverify?: (id: string) => void;
  reverifyingId?: string | null;
  reverifyDisabled?: boolean;
}) {
  useEffect(() => {
    if (!selectedId) return;
    document
      .getElementById(`evcard-${selectedId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedId]);

  if (evidence.length === 0) return null;
  const groups = new Map<string, EvidenceItem[]>();
  for (const item of evidence) {
    const label = CATEGORY_LABELS[item.category] ?? item.category;
    const list = groups.get(label) ?? [];
    list.push(item);
    groups.set(label, list);
  }
  const superseded = new Map<string, EvidenceRefresh>();
  for (const r of refreshes ?? []) {
    superseded.set(r.old_evidence_id, r);
  }
  return (
    <section className="card">
      <div className="card-head">
        <h2>Evidence</h2>
        <span className="muted">
          {evidence.length} items &middot; {groups.size} categor
          {groups.size === 1 ? "y" : "ies"}
        </span>
      </div>
      {[...groups.entries()].map(([label, items]) => (
        <div key={label} className="evidence-group">
          <h3 className="evidence-group-head">
            {label} <span className="muted">({items.length})</span>
          </h3>
          <div className="evidence-list">
            {items.map((item) => (
              <article
                key={item.id}
                id={`evcard-${item.id}`}
                className={item.id === selectedId ? "evidence-item ev-selected" : "evidence-item"}
              >
                <div className="evidence-head">
                  <button
                    type="button"
                    className="chip chip-button"
                    onClick={() => onSelect(item.id)}
                    title="Select this evidence"
                  >
                    {item.id}
                  </button>
                  <strong>{item.category}</strong>
                  <code className="mono muted">{item.source}</code>
                  <span className="muted ev-time">
                    {new Date(item.collected_at).toLocaleString()}
                  </span>
                </div>
                <div className="evidence-flags">
                  {item.refresh_of && (
                    <span className="flag flag-current">RE-CHECK OF {item.refresh_of}</span>
                  )}
                  {superseded.has(item.id) && (
                    <span className="flag flag-historical">
                      HISTORICAL — SUPERSEDED BY {superseded.get(item.id)?.new_evidence_id} (
                      {superseded.get(item.id)?.verdict.toUpperCase()})
                    </span>
                  )}
                  {onReverify && item.tool_name && (
                    <button
                      type="button"
                      className="link-button"
                      disabled={reverifyDisabled || reverifyingId === item.id}
                      onClick={() => onReverify(item.id)}
                      title={`Re-run ${item.tool_name} with identical arguments`}
                    >
                      {reverifyingId === item.id ? "Re-checking…" : "Re-check"}
                    </button>
                  )}
                </div>
                {dataWarnings(item).map((w, i) => (
                  <p key={i} className="warn ev-warning">
                    {w}
                  </p>
                ))}
                {item.error ? (
                  <p className="item-error">Collection error: {item.error}</p>
                ) : superseded.has(item.id) ? (
                  <details className="ev-historical-details">
                    <summary>Superseded JSON &mdash; expand to compare with current</summary>
                    <pre className="pre">{JSON.stringify(item.data, null, 2)}</pre>
                  </details>
                ) : (
                  <>
                    <pre className="pre">{previewText(item)}</pre>
                    <details>
                      <summary>Full JSON</summary>
                      <pre className="pre">{JSON.stringify(item.data, null, 2)}</pre>
                    </details>
                  </>
                )}
              </article>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
