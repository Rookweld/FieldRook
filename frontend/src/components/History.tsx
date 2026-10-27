import { useEffect, useState } from "react";
import { ApiError, getInvestigation, listInvestigations } from "../api";
import type { InvestigationResponse, InvestigationSummary } from "../types";

export function History({ onOpen }: { onOpen: (inv: InvestigationResponse) => void }) {
  const [items, setItems] = useState<InvestigationSummary[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listInvestigations().then(
      (rows) => {
        if (!cancelled) setItems(rows);
      },
      (e: unknown) => {
        if (!cancelled) {
          setError(
            e instanceof ApiError ? `History failed (HTTP ${e.status}): ${e.message}` : String(e),
          );
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const open = async (id: string) => {
    if (busy) return;
    setBusy(id);
    setError(null);
    try {
      onOpen(await getInvestigation(id));
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Open failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card">
      <div className="card-head">
        <h2>Incident history</h2>
        <span className="muted">{items.length} investigations · persisted in SQLite</span>
      </div>
      {error && <p className="warn">{error}</p>}
      {items.length === 0 && !error && (
        <p className="muted">No investigations stored yet.</p>
      )}
      <ol className="history-list">
        {items.map((item) => (
          <li key={item.investigation_id} className="history-item">
            <div className="history-main">
              <button
                type="button"
                className="link-button history-title"
                disabled={busy !== null}
                onClick={() => void open(item.investigation_id)}
              >
                {busy === item.investigation_id ? "Opening…" : item.problem}
              </button>
              <span className="history-meta">
                {new Date(item.created_at).toLocaleString()} · {item.status} ·{" "}
                {item.evidence_count} evidence · {item.proposal_count} proposals
              </span>
              <span className="history-meta mono">{item.investigation_id}</span>
            </div>
            <div className="history-links">
              {item.latest_outcome && (
                <span
                  className={
                    item.latest_outcome === "VERIFIED_RESOLVED"
                      ? "badge badge-verified"
                      : item.latest_outcome === "NOT_RESOLVED"
                        ? "badge badge-fail"
                        : "badge"
                  }
                >
                  {item.latest_outcome}
                </span>
              )}
              <a
                className="link-button"
                href={`/api/investigations/${encodeURIComponent(item.investigation_id)}/export?format=markdown`}
              >
                Markdown
              </a>
              <a
                className="link-button"
                href={`/api/investigations/${encodeURIComponent(item.investigation_id)}/export?format=json`}
              >
                JSON
              </a>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
