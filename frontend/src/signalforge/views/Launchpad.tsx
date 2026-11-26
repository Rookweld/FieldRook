import { useState } from "react";
import type { LaunchpadProps } from "../types";
import type { CaseDisposition } from "../../types";
import { caseDispositionLabel } from "../../casePresentation";
import { useExport } from "../hooks/useExport";
import { RookFigure } from "../components/Shell";
import "./Launchpad.css";

const RECENT_PREVIEW = 5;
type CaseFilter = "all" | CaseDisposition;
const FILTERS: { id: CaseFilter; label: string }[] = [
  { id: "all", label: "All recent" },
  { id: "open", label: "Open" },
  { id: "needs_followup", label: "Follow-up" },
  { id: "handed_off", label: "Handed off" },
  { id: "resolved", label: "Resolved" },
];

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
  const [filter, setFilter] = useState<CaseFilter>("all");
  const { busy: exportBusy, error: exportError, downloadInvestigation } = useExport();
  const search = query.trim().toLocaleLowerCase();
  const scoped = filter === "all" ? recents : recents.filter(
    (item) => (item.disposition ?? "open") === filter,
  );
  const filtered = search
    ? scoped.filter((item) =>
        `${item.problem} ${item.status} ${item.disposition ?? "open"} ${item.investigation_id}`.toLocaleLowerCase().includes(search),
      )
    : scoped;
  const visible = search || showAll ? filtered : filtered.slice(0, RECENT_PREVIEW);
  const followUps = recents.filter((item) => item.disposition === "needs_followup");
  const openCases = recents.filter((item) => (item.disposition ?? "open") === "open");
  const continueCase = followUps[0] ?? openCases[0] ?? recents[0] ?? null;
  // Keep the landing context truthful: this is backend connectivity, not a
  // claim that diagnostics or the model are healthy.
  const connectionLabel = status ? "Workspace connected" : "Connecting to workspace";

  return (
    <section className="sf-screen" aria-label="Launchpad">
      <div className="sf-home-context" role="status">
        <span className={status ? "sf-home-connection is-connected" : "sf-home-connection"}>
          <span className="sf-connection-dot" aria-hidden="true" />
          {connectionLabel}
        </span>
        <span className="sf-home-counts" aria-label="Investigation overview">
          <span><strong>{openCases.length}</strong> open</span>
          <span><strong>{followUps.length}</strong> follow-up</span>
          <span><strong>{recents.length}</strong> total</span>
        </span>
      </div>
      <div className={recents.length > 0 ? "sf-homehero sf-homehero-compact" : "sf-homehero"}>
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
            Start a new investigation ↗
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
          <div className="sf-history-filters" role="group" aria-label="Filter investigations by case status">
            {FILTERS.map((item) => {
              const count = item.id === "all"
                ? recents.length
                : recents.filter((entry) => (entry.disposition ?? "open") === item.id).length;
              return (
                <button type="button" key={item.id}
                  className={filter === item.id ? "sf-history-filter sf-history-filter-active" : "sf-history-filter"}
                  aria-pressed={filter === item.id}
                  onClick={() => { setFilter(item.id); setShowAll(false); }}>
                  {item.label} <span>{count}</span>
                </button>
              );
            })}
          </div>
          <input
            className="sf-history-search"
            type="search"
            aria-label="Search recent investigations"
            placeholder="Search cases by problem or status…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {exportBusy && (
            <p className="sf-minihelp" role="status">
              Preparing export… your browser or Windows may ask where to save it.
            </p>
          )}
          {exportError && <p className="sf-warn" role="alert">{exportError}</p>}
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
                : filter !== "all"
                  ? "No recent cases in this status. Try another filter."
                  : "No investigations on record yet. Start one above to save the first case here."}
            </p>
          ) : (
            <div className="sf-recent" aria-label="Recent case results">
              {visible.map((item) => (
                <div className="sf-recent-row" key={item.investigation_id}>
                  <button
                    type="button"
                    className="sf-recent-open"
                    disabled={openingId !== null}
                    onClick={() => onOpen(item.investigation_id)}
                    title={`Updated ${new Date(item.updated_at).toLocaleString()} · ${item.evidence_count} evidence · ${item.proposal_count} proposals`}
                  >
                    {openingId === item.investigation_id ? "Opening…" : item.problem}
                  </button>
                  <span className="sf-recent-meta">
                    Updated {new Date(item.updated_at).toLocaleDateString()} · {item.evidence_count} evidence
                  </span>
                  <span className="sf-recent-links">
                    <button type="button" disabled={exportBusy !== null}
                      aria-label={`Save Markdown report for ${item.investigation_id}`}
                      onClick={() => void downloadInvestigation(item.investigation_id, "markdown")}>
                      Report
                    </button>
                    <button type="button" disabled={exportBusy !== null}
                      aria-label={`Export JSON for ${item.investigation_id}`}
                      onClick={() => void downloadInvestigation(item.investigation_id, "json")}>
                      Data
                    </button>
                  </span>
                  <span className="sf-recent-status">
                    {caseDispositionLabel(item.disposition, true)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        {continueCase ? (
          <div className="sf-paper-panel sf-continue-panel">
            <h3>CONTINUE YOUR WORK</h3>
            <div className="sf-continue-stats" aria-label="Case status counts">
              <div><strong>{openCases.length}</strong><span>OPEN</span></div>
              <div><strong>{followUps.length}</strong><span>FOLLOW-UP</span></div>
            </div>
            <p className="sf-continue-label">
              {continueCase.disposition === "needs_followup" ? "WAITING FOR FOLLOW-UP" : "RECENT CASE"}
            </p>
            <p className="sf-continue-problem">{continueCase.problem}</p>
            <p className="sf-continue-meta">
              Last updated {new Date(continueCase.updated_at).toLocaleString()}
            </p>
            <button type="button" className="sf-btn sf-btn-lime"
              disabled={openingId !== null}
              onClick={() => onOpen(continueCase.investigation_id)}>
              {continueCase.disposition === "resolved" || continueCase.disposition === "handed_off"
                ? "Review case"
                : "Continue case"}
            </button>
            <p className="sf-minihelp">
              Cases are filed by technicians. A reported resolution is not necessarily a verified repair.
              The list on the left shows the most recent records.
            </p>
          </div>
        ) : (
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
        )}
      </div>
    </section>
  );
}
