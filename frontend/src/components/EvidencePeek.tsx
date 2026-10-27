import { Fragment, useEffect, useRef } from "react";
import { summarizeEvidence } from "../evidenceSummary";
import type { EvidenceItem } from "../types";

export function EvidencePeek({
  evidence,
  selectedId,
  onClose,
  onNavigate,
}: {
  evidence: EvidenceItem[];
  selectedId: string | null;
  onClose: () => void;
  onNavigate?: (id: string) => void;
}) {
  const selected = evidence.find((item) => item.id === selectedId) ?? null;
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!selected) return;
    openerRef.current = document.activeElement;
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      if (openerRef.current instanceof HTMLElement) openerRef.current.focus();
    };
  }, [selected?.id, onClose]);

  if (!selected) return null;

  const warnings = Array.isArray(selected.data["warnings"])
    ? selected.data["warnings"].filter((value): value is string => typeof value === "string")
    : [];

  return (
    <aside className="evidence-peek" role="region" aria-label={`Evidence ${selected.id} quick view`}>
      <div className="evidence-peek-head">
        <div>
          <strong>
            {selected.id} · {selected.category.replace(/_/g, " ")}
          </strong>
          <div className="muted evidence-peek-meta">
            <div>{selected.source}</div>
            <div>{new Date(selected.collected_at).toLocaleString()}</div>
          </div>
        </div>
        <button
          ref={closeRef}
          type="button"
          className="evidence-peek-close"
          onClick={onClose}
          aria-label="Close evidence preview"
        >
          ×
        </button>
      </div>
      {selected.error ? (
        <p className="item-error">Collection error: {selected.error}</p>
      ) : (
        <dl className="ev-summary">
          {summarizeEvidence(selected)
            .slice(0, 6)
            .map((row, i) => (
              <Fragment key={`${row.label}-${i}`}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </Fragment>
            ))}
        </dl>
      )}
      {warnings.length > 0 && <p className="warn">{warnings.join("; ")}</p>}
      <div className="evidence-peek-actions">
        {onNavigate && (
          <button type="button" className="link-button" onClick={() => onNavigate(selected.id)}>
            Go to full evidence
          </button>
        )}
        <button type="button" className="link-button" onClick={onClose}>
          Close
        </button>
      </div>
    </aside>
  );
}
