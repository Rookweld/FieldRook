import { Fragment, useState } from "react";
import { summarizeEvidence } from "../../evidenceSummary";
import type { EvidenceViewProps } from "../types";
import "./Utility.css";

export function EvidenceView({ investigation, onGoWorkbench, onGoLaunchpad }: EvidenceViewProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (!investigation) {
    return (
      <section className="sf-screen" aria-label="Evidence">
        <div className="sf-utility">
          <div className="sf-eyebrow">The source of truth</div>
          <h1>
            EVERY CLUE
            <br />
            HAS A SOURCE.
          </h1>
          <p>
            No case is open. Evidence inspection needs an active investigation to read records
            from.
          </p>
          <div className="sf-utility-card">
            <h2>Open a case first</h2>
            <p>
              Pick a past investigation from the Launchpad, or start a new one in the Workbench.
              Collected records will appear here with their origin, scope, and age.
            </p>
            <button type="button" className="sf-btn sf-btn-lime" onClick={onGoLaunchpad}>
              GO TO LAUNCHPAD ⌂
            </button>
            <button type="button" className="sf-btn sf-btn-dark" onClick={onGoWorkbench}>
              GO TO WORKBENCH ↗
            </button>
          </div>
        </div>
      </section>
    );
  }

  const evidence = investigation.evidence;
  const effectiveId = selectedId ?? evidence[0]?.id ?? null;
  const selected = evidence.find((item) => item.id === effectiveId) ?? null;
  const categories = [...new Set(evidence.map((item) => item.category))].sort();
  const failed = evidence.filter((item) => item.error !== null).length;

  return (
    <section className="sf-screen" aria-label="Evidence">
      <div className="sf-utility">
        <div className="sf-eyebrow">The source of truth</div>
        <h1>
          EVERY CLUE
          <br />
          HAS A SOURCE.
        </h1>
        <p>
          {evidence.length} records on this case
          {failed > 0 ? ` · ${failed} failed to collect` : " · none failed to collect"}.
          Origin, scope, and age determine what each record can support.
        </p>
        <div className="sf-utility-card">
          <h2>What counts as evidence?</h2>
          {categories.length === 0 ? (
            <p>No records yet — diagnostic results land here as they are collected.</p>
          ) : (
            categories.map((category) => (
              <span className="sf-small-token" key={category}>
                {category} · {evidence.filter((item) => item.category === category).length}
              </span>
            ))
          )}
          <p>
            These categories are never collapsed into a single confidence number. Re-checks and
            contradictions stay visible beside the records they affect.
          </p>
        </div>
        {evidence.length > 0 && (
          <div className="sf-ev-split">
            <div className="sf-utility-card" role="group" aria-label="Case evidence records">
              <h2>Records</h2>
              <div className="sf-ev-list" style={{ padding: 0 }}>
                {evidence.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={item.id === effectiveId ? "sf-evbtn sf-active" : "sf-evbtn"}
                    aria-current={item.id === effectiveId ? "true" : undefined}
                    onClick={() => setSelectedId(item.id)}
                  >
                    <span className="sf-ev-ic" aria-hidden="true">
                      {item.error ? "!" : "◎"}
                    </span>
                    <span className="sf-evtxt">
                      <strong>{item.tool_name ?? item.category}</strong>
                      <small>
                        {item.source} &middot; {new Date(item.collected_at).toLocaleString()}
                      </small>
                    </span>
                    <span className="sf-ev-status">{item.error ? "ERROR" : "HELD"}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="sf-utility-card sf-ev-detail">
              {selected ? (
                <>
                  <div className="sf-eyebrow">
                    {selected.category} &middot; {selected.source}
                  </div>
                  <h3>{selected.tool_name ?? selected.id}</h3>
                  <dl className="sf-kv">
                    <dt>Record</dt>
                    <dd>{selected.id}</dd>
                    <dt>Collected</dt>
                    <dd>{new Date(selected.collected_at).toLocaleString()}</dd>
                    {selected.tool_name && (
                      <>
                        <dt>Tool</dt>
                        <dd>{selected.tool_name}</dd>
                      </>
                    )}
                    {selected.error ? (
                      <>
                        <dt>Error</dt>
                        <dd>{selected.error}</dd>
                      </>
                    ) : (
                      summarizeEvidence(selected)
                        .slice(0, 6)
                        .map((row) => (
                          <Fragment key={row.label}>
                            <dt>{row.label}</dt>
                            <dd>{row.value}</dd>
                          </Fragment>
                        ))
                    )}
                    {selected.refresh_of && (
                      <>
                        <dt>Re-check of</dt>
                        <dd>{selected.refresh_of}</dd>
                      </>
                    )}
                  </dl>
                  <details>
                    <summary>Raw record data</summary>
                    <pre>{JSON.stringify(selected.data, null, 2)}</pre>
                  </details>
                </>
              ) : (
                <p>Select a record to inspect it.</p>
              )}
            </div>
          </div>
        )}
        {investigation.refreshes.length > 0 && (
          <div className="sf-utility-card">
            <h2>Re-checks ({investigation.refreshes.length})</h2>
            {investigation.refreshes.map((refresh) => (
              <p key={`${refresh.old_evidence_id}-${refresh.compared_at}`}>
                {refresh.tool_name}: {refresh.verdict} ·{" "}
                {new Date(refresh.compared_at).toLocaleString()}
                {refresh.changes.length > 0 ? ` · ${refresh.changes.join("; ")}` : ""}
              </p>
            ))}
          </div>
        )}
        <div className="sf-utility-card">
          <h2>Case timeline ({investigation.activity.length})</h2>
          {investigation.activity.length === 0 ? (
            <p>No activity recorded yet on this case.</p>
          ) : (
            <ol className="sf-timeline">
              {investigation.activity.map((record) => (
                <li key={record.seq}>
                  <span className="sf-seq">#{record.seq}</span>
                  <strong>{record.title}</strong>
                  {record.detail && <p>{record.detail}</p>}
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}
