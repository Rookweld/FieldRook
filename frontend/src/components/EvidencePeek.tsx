import { useEffect } from "react";
import type { EvidenceItem } from "../types";

export function EvidencePeek({
  evidence,
  selectedId,
  onClose,
}: {
  evidence: EvidenceItem[];
  selectedId: string | null;
  onClose: () => void;
}) {
  const selected = evidence.find((item) => item.id === selectedId);
  useEffect(() => {
    if (!selected) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selected, onClose]);

  if (!selected) return null;

  const pretty = JSON.stringify(selected.data, null, 2);
  const summary = pretty.length > 380 ? `${pretty.slice(0, 380)}…` : pretty;
  const warnings = Array.isArray(selected.data["warnings"])
    ? selected.data["warnings"].filter((value): value is string => typeof value === "string")
    : [];

  return (
    <aside className="evidence-peek" role="region" aria-label={`Evidence ${selected.id} quick view`}>
      <div className="evidence-peek-head">
        <div>
          <strong>{selected.id} · {selected.category.replace(/_/g, " ")}</strong>
          <div className="muted evidence-peek-meta">{selected.source} · {new Date(selected.collected_at).toLocaleString()}</div>
        </div>
        <button type="button" className="evidence-peek-close" onClick={onClose} aria-label="Close evidence preview">×</button>
      </div>
      {selected.error ? <p className="item-error">{selected.error}</p> : <pre className="evidence-peek-preview">{summary}</pre>}
      {warnings.length > 0 && <p className="warn">{warnings.join("; ")}</p>}
      <div className="evidence-peek-actions">
        <button type="button" className="link-button" onClick={() => {
          document.getElementById(`evcard-${selected.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
        }}>Go to full evidence</button>
        <button type="button" className="link-button" onClick={onClose}>Close</button>
      </div>
    </aside>
  );
}
