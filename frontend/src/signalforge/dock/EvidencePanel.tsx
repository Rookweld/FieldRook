import { useState } from "react";
import { summarizeEvidence } from "../../evidenceSummary";
import type { EvidenceRailProps } from "../types";
import { SignalTrace } from "../motion";

export type EvidencePanelProps = EvidenceRailProps & {
  /**
   * Controlled selection (FIELD KIT dock). When onSelectEvidence is set,
   * the dock owns the selected record id so switching instruments never
   * loses it. Otherwise the panel keeps its own M026-local selection.
   */
  selectedId?: string | null;
  onSelectEvidence?: (id: string) => void;
};

/**
 * The M026 evidence rail, preserved verbatim behind the FIELD KIT
 * Evidence tab. Rendering is unchanged; only selection ownership moved
 * up to the dock so tool switches preserve it.
 */
export function EvidencePanel({
  view,
  investigation,
  onGoEvidence,
  onGoWorkbench,
  selectedId: controlledId,
  onSelectEvidence,
}: EvidencePanelProps) {
  const evidence = investigation?.evidence ?? [];
  const [localId, setLocalId] = useState<string | null>(null);
  const selectedId = onSelectEvidence ? controlledId : localId;
  const effectiveId = selectedId ?? evidence[0]?.id ?? null;
  const selected = evidence.find((item) => item.id === effectiveId) ?? null;
  const summary = selected ? summarizeEvidence(selected).slice(0, 3) : [];

  const select = (id: string) => {
    if (onSelectEvidence) onSelectEvidence(id);
    else setLocalId(id);
  };

  return (
    <>
      <div className="sf-rail-header">
        <div className="sf-small">PROVENANCE / CASE RECORDS</div>
        <h2>
          EVIDENCE<span>.</span>
        </h2>
        <div className="sf-sub">
          {investigation ? `${evidence.length} records on this case` : "No active investigation"}
        </div>
      </div>
      {evidence.length === 0 ? (
        <p className="sf-rail-empty">
          {investigation
            ? "No evidence collected yet. Diagnostic results and technician notes will appear here with their source."
            : "Open a case from the Launchpad or start one in the Workbench — collected evidence will appear here with its source."}
        </p>
      ) : (
        <div className="sf-ev-list" role="group" aria-label="Case evidence">
          {evidence.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === effectiveId ? "sf-evbtn sf-active" : "sf-evbtn"}
              aria-current={item.id === effectiveId ? "true" : undefined}
              onClick={() => select(item.id)}
            >
              <span className="sf-ev-ic" aria-hidden="true">
                {item.error ? "!" : "◎"}
              </span>
              <span className="sf-evtxt">
                <strong>{item.tool_name ?? item.category}</strong>
                <small>
                  {item.source} &middot; {new Date(item.collected_at).toLocaleDateString()}
                </small>
              </span>
              <span className="sf-ev-status">{item.error ? "ERROR" : item.category}</span>
            </button>
          ))}
        </div>
      )}
      <div className="sf-wavebox" data-motion-slot="signal-trace">
        <div className="sf-section-label">INSTRUMENT / UI ACTIVITY ONLY</div>
        <h3>Quiet instrument.</h3>
        <p>
          Animated activity cue. It is <strong>not</strong> a live health or network measurement.
        </p>
        <SignalTrace activityPulse={investigation?.activity.length ?? 0} />
        <div className="sf-signal-label">◉ AMBIENT / IDLE</div>
      </div>
      <div className="sf-inspector" aria-live="polite">
        {selected ? (
          <>
            <div className="sf-badge-line">
              {selected.category} &middot; {selected.source}
            </div>
            <h4>{selected.tool_name ?? selected.id}</h4>
            {selected.error ? (
              <p>Collection failed: {selected.error}</p>
            ) : summary.length > 0 ? (
              summary.map((row) => (
                <p key={row.label}>
                  {row.label}: {row.value}
                </p>
              ))
            ) : (
              <p>Record held; open the full evidence view for raw detail.</p>
            )}
            {view !== "evidence" && (
              <p>
                <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoEvidence}>
                  Full evidence view ↗
                </button>
              </p>
            )}
          </>
        ) : (
          <>
            <div className="sf-badge-line">NO RECORD SELECTED</div>
            <h4>Nothing to inspect</h4>
            {view !== "workbench" && (
              <p>
                <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoWorkbench}>
                  Go to Workbench ↗
                </button>
              </p>
            )}
          </>
        )}
      </div>
    </>
  );
}
