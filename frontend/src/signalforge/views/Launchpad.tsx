import { useState } from "react";
import type { LaunchpadProps } from "../types";
import { RookFigure } from "../components/Shell";
import "./Launchpad.css";

const RECENT_PREVIEW = 5;

export function Launchpad({
  status,
  recents,
  recentsLoading,
  recentsError,
  notice,
  openingId,
  onNew,
  onImport,
  onOpen,
  onRetryRecents,
}: LaunchpadProps) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? recents : recents.slice(0, RECENT_PREVIEW);

  return (
    <section className="sf-screen" aria-label="Launchpad">
      <div className="sf-homehero">
        <RookFigure />
        <div className="sf-eyebrow">Diagnose / Verify / Resolve</div>
        <h1>
          BE CURIOUS.
          <br />
          <span>BE CERTAIN.</span>
        </h1>
        <p>
          The technician&apos;s workbench. Less guessing. Better evidence. One useful step at a
          time.
        </p>
        <div className="sf-home-actions">
          <button type="button" className="sf-btn sf-btn-lime" onClick={onNew}>
            + New investigation ↗
          </button>
          <button type="button" className="sf-btn sf-btn-dark" onClick={onImport}>
            ⇩ Import Collector package
          </button>
        </div>
      </div>
      <div className="sf-home-panels">
        <div className="sf-paper-panel">
          <h3>
            RECENT INVESTIGATIONS{" "}
            {recents.length > RECENT_PREVIEW && (
              <button
                type="button"
                className="sf-viewall"
                onClick={() => setShowAll((all) => !all)}
                aria-expanded={showAll}
              >
                {showAll ? "SHOW LESS" : `VIEW ALL ${recents.length} ↗`}
              </button>
            )}
          </h3>
          {notice && (
            <p className="sf-warn" role="alert">
              {notice}
            </p>
          )}
          {recentsLoading ? (
            <p className="sf-minihelp">Loading recent investigations from this machine…</p>
          ) : recentsError ? (
            <div>
              <p className="sf-warn" role="alert">
                {recentsError}
              </p>
              <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onRetryRecents}>
                Retry
              </button>
            </div>
          ) : visible.length === 0 ? (
            <p className="sf-minihelp">
              No investigations on record yet. Start one above — it will appear here with its
              status and export links.
            </p>
          ) : (
            <div className="sf-recent">
              {visible.map((item) => (
                <div className="sf-recent-row" key={item.investigation_id}>
                  <button
                    type="button"
                    className="sf-recent-open"
                    disabled={openingId !== null}
                    onClick={() => onOpen(item.investigation_id)}
                    title={`${new Date(item.created_at).toLocaleString()} · ${item.status} · ${item.evidence_count} evidence · ${item.proposal_count} proposals`}
                  >
                    {openingId === item.investigation_id ? "Opening…" : item.problem}
                  </button>
                  <span className="sf-recent-meta">
                    {new Date(item.created_at).toLocaleDateString()} · {item.evidence_count}{" "}
                    evidence
                  </span>
                  <span className="sf-recent-links">
                    <a
                      href={`/api/investigations/${encodeURIComponent(item.investigation_id)}/export?format=markdown`}
                    >
                      Markdown
                    </a>
                    <a
                      href={`/api/investigations/${encodeURIComponent(item.investigation_id)}/export?format=json`}
                    >
                      JSON
                    </a>
                  </span>
                  <span className="sf-recent-status">{item.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="sf-paper-panel">
          <h3>THE INSTRUMENT PANEL</h3>
          <div className="sf-system-stat">
            <div className="sf-stat">
              <strong>{recentsLoading ? "…" : recents.length}</strong>
              <span>INVESTIGATIONS ON RECORD</span>
            </div>
            <div className="sf-stat sf-stat-lime">
              <strong>{status ? status.model_mode.toUpperCase() : "…"}</strong>
              <span>REASONING ENGINE MODE</span>
            </div>
          </div>
          <p className="sf-minihelp">
            {status
              ? `Connected: ${status.service} v${status.version} on ${status.platform}. Diagnostics: ${status.live_diagnostics_available ? "live read-only tools on this machine" : "synthetic fixtures only"}.`
              : "Waiting for the FieldRook backend on this machine. The workbench stays usable and connects automatically."}
          </p>
        </div>
      </div>
    </section>
  );
}
