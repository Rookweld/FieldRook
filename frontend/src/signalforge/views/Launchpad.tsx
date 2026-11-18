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
  const [query, setQuery] = useState("");
  const search = query.trim().toLocaleLowerCase();
  const filtered = search
    ? recents.filter((item) =>
        `${item.problem} ${item.status} ${item.investigation_id}`.toLocaleLowerCase().includes(search),
      )
    : recents;
  const visible = search || showAll ? filtered : filtered.slice(0, RECENT_PREVIEW);

  return (
    <section className="sf-screen" aria-label="Launchpad">
      <div className="sf-homehero">
        <RookFigure />
        <div className="sf-eyebrow">Diagnose / Verify / Resolve</div>
        <h1>
          FOLLOW THE
          <br />
          <span>EVIDENCE.</span>
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
            {filtered.length > RECENT_PREVIEW && !search && (
              <button
                type="button"
                className="sf-viewall"
                onClick={() => setShowAll((all) => !all)}
                aria-expanded={showAll}
              >
                {showAll ? "SHOW LESS" : `VIEW ALL ${filtered.length} ↗`}
              </button>
            )}
          </h3>
          <input
            className="sf-history-search"
            type="search"
            aria-label="Search recent investigations"
            placeholder="Search cases by problem or status…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
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
              {search
                ? "No recent investigations match that search."
                : "No investigations on record yet. Start one above to save the first case here."}
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
        <div className="sf-paper-panel sf-start-panel">
          <h3>ONE CLEAR PATH THROUGH A CASE</h3>
          <ol className="sf-start-steps">
            <li>
              <span>01</span>
              <div><strong>Describe the problem</strong><p>Report what fails and which machine is affected.</p></div>
            </li>
            <li>
              <span>02</span>
              <div><strong>Follow the next check</strong><p>Keep reported facts separate from measured evidence.</p></div>
            </li>
            <li>
              <span>03</span>
              <div><strong>Verify and export</strong><p>Record the outcome before closing or handing off the case.</p></div>
            </li>
          </ol>
          <p className="sf-minihelp" role="status">
            {status
              ? status.live_diagnostics_available
                ? "This machine supports read-only host diagnostics. Authorization is still required for sensitive actions."
                : "Demo diagnostics are in use. Results are not live observations of a real PC."
              : "Backend connection pending. Availability will appear when the service responds."}
          </p>
        </div>
      </div>
    </section>
  );
}
