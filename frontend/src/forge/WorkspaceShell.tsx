import { DiscoveredRail } from "./DiscoveredRail";
import { HappeningNow } from "./HappeningNow";
import { KnowledgeCiteChip } from "./KnowledgeCiteChip";
import { NextUpQueue } from "./NextUpQueue";
import { RespondDock } from "./RespondDock";
import type { WorkspaceShellProps } from "./types";
import "./forge.css";

/**
 * Unified technician workspace. Composes the four investigation views —
 * HappeningNow, DiscoveredRail, NextUpQueue, RespondDock — over one full
 * InvestigationResponse with full-replace onUpdate. CollectorImportCard and
 * IntakeCollectorCard stay standalone for lead placement (evidence view /
 * intake form); the optional citations strip renders only when the lead
 * passes references + citations.
 */
export function WorkspaceShell({
  investigation,
  onUpdate,
  onEvidenceClick,
  onAction,
  onView,
  onError,
  disabled,
  hideDockComposer,
  hideDockNotes,
  references,
  citations,
}: WorkspaceShellProps) {
  const passageFor = (docId: string) => (references ?? []).find((p) => p.doc_id === docId) ?? null;

  return (
    <div className="forge-shell" data-testid="forge-workspace" aria-label="Technician workspace">
      <HappeningNow investigation={investigation} onEvidenceClick={onEvidenceClick} />
      <div className="forge-cols">
        <DiscoveredRail
          investigation={investigation}
          onEvidenceClick={onEvidenceClick}
          onOpen={onView ? () => onView("evidence") : undefined}
        />
        <NextUpQueue investigation={investigation} onAction={onAction} onView={onView} />
      </div>
      <RespondDock
        investigation={investigation}
        onUpdate={onUpdate}
        onError={onError}
        disabled={disabled}
        hideComposer={hideDockComposer}
        hideNotes={hideDockNotes}
      />
      {(citations ?? []).length > 0 && (
        <section className="card forge-cites" data-testid="forge-citations" aria-label="Reference citations">
          <div className="card-head">
            <h2>
              <span className="eyebrow">References</span>
            </h2>
            <span className="muted">quoted excerpts · display only</span>
          </div>
          <div className="forge-chip-row">
            {(citations ?? []).map((citation) => (
              <KnowledgeCiteChip
                key={citation.doc_id}
                citation={citation}
                passage={passageFor(citation.doc_id)}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
