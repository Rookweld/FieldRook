import { useEffect } from "react";
import type { EvidenceItem } from "../types";

const PREVIEW_CHARS = 500;

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
  return (
    <section className="card">
      <div className="card-head">
        <h2>Evidence</h2>
        <span className="muted">{evidence.length} items</span>
      </div>
      <div className="evidence-list">
        {evidence.map((item) => (
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
    </section>
  );
}
