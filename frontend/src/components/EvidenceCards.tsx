import { useEffect } from "react";
import type { EvidenceItem } from "../types";

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

function previewText(item: EvidenceItem): string {
  const pretty = JSON.stringify(item.data, null, 2);
  if (pretty.length <= PREVIEW_CHARS) return pretty;
  return `${pretty.slice(0, PREVIEW_CHARS)}\n\u2026 (+${pretty.length - PREVIEW_CHARS} chars, see full JSON)`;
}

export function EvidenceCards({
  evidence,
  selectedId,
  onSelect,
}: {
  evidence: EvidenceItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
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
                </div>
                {item.error ? (
                  <p className="item-error">Collection error: {item.error}</p>
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
