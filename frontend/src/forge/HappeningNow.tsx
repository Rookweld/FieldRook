import { EvidenceChip } from "../components/EvidenceChip";
import { headlineEvidence } from "../components/evidence/EvidenceVisual";
import type { HappeningNowProps } from "./types";
import "./forge.css";

/**
 * One-line context (stage + blocked/assistant/understanding) followed by
 * key observations and open unknowns, all cited to real evidence ids.
 * Pure render of `investigation`; no fetching, no mutation.
 */
export function HappeningNow({ investigation, onEvidenceClick }: HappeningNowProps) {
  const contextLine =
    investigation.blocked_reason ??
    investigation.assistant_message ??
    investigation.understanding ??
    "";
  const causes = investigation.assessment?.causes ?? [];
  const observations = causes
    .flatMap((cause) => cause.evidence_ids)
    .map((eid) => {
      const item = investigation.evidence.find((e) => e.id === eid);
      return item ? { id: eid, item } : null;
    })
    .filter((o): o is { id: string; item: (typeof investigation.evidence)[number] } => o !== null)
    .slice(0, 3);
  const unknowns = [
    ...(investigation.assessment?.uncertainties ?? []),
    ...(investigation.assessment?.missing_evidence ?? []),
  ];

  return (
    <section className="card forge-now" data-testid="forge-happening-now" aria-label="Happening now">
      <div className="card-head">
        <h2>
          <span className="eyebrow">Happening now</span>
        </h2>
        <span className="badge" title="Current lifecycle stage">
          {investigation.stage.replace(/_/g, " ")}
        </span>
      </div>
      {contextLine ? (
        <p className="forge-context">{contextLine}</p>
      ) : (
        <p className="muted">No assistant context recorded yet for this investigation.</p>
      )}
      <div className="forge-now-cols">
        <div>
          <h3 className="story-head">Key observations</h3>
          {observations.length === 0 ? (
            <p className="muted">No cited observations yet.</p>
          ) : (
            <ul className="story-obs">
              {observations.map((o) => {
                const head = headlineEvidence(o.item);
                return (
                  <li key={o.id}>
                    <EvidenceChip id={o.id} onSelect={onEvidenceClick} />
                    <span className="story-noun">{head.noun}</span>
                    <span>{head.text}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div>
          <h3 className="story-head">
            Still unknown {unknowns.length > 0 && <span className="muted">({unknowns.length})</span>}
          </h3>
          {unknowns.length === 0 ? (
            <p className="muted">No open uncertainties recorded.</p>
          ) : (
            <ul className="story-unknowns">
              {unknowns.slice(0, 3).map((u, i) => (
                <li key={i}>{u}</li>
              ))}
            </ul>
          )}
          {unknowns.length > 3 && (
            <p className="muted">+{unknowns.length - 3} more in the full diagnosis.</p>
          )}
        </div>
      </div>
    </section>
  );
}
