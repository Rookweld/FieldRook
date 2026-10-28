import { EvidenceChip } from "../components/EvidenceChip";
import { FORGE_CATEGORY_LABELS, type DiscoveredRailProps } from "./types";
import "./forge.css";

/**
 * Coverage + counts + contradictions rail. Coverage groups reuse the exact
 * OverviewPanel category labels; contradictions render with cited evidence
 * chips. `onOpen` navigates to the Evidence view (shell: onView("evidence")).
 */
export function DiscoveredRail({ investigation, onEvidenceClick, onOpen }: DiscoveredRailProps) {
  const usable = investigation.evidence.filter((e) => !e.error);
  const failed = investigation.evidence.filter((e) => e.error);
  const groups = new Map<string, number>();
  for (const item of usable) {
    const label = FORGE_CATEGORY_LABELS[item.category] ?? item.category;
    groups.set(label, (groups.get(label) ?? 0) + 1);
  }

  return (
    <section
      className="card forge-rail"
      data-testid="forge-discovered-rail"
      aria-label="Discovered evidence"
    >
      <div className="card-head">
        <h2>
          <span className="eyebrow">Discovered</span>
        </h2>
        <span className="muted" data-testid="forge-rail-counts">
          {usable.length} usable · {failed.length} failed · {investigation.contradictions.length}{" "}
          contradictions
        </span>
      </div>
      <ul className="forge-coverage" aria-label="Coverage by area">
        {[...groups.entries()].map(([label, count]) => (
          <li key={label}>
            <button
              type="button"
              className="coverage"
              onClick={() => onOpen?.()}
              title="Open the Evidence view"
            >
              <strong>{label}</strong> ({count})
            </button>
          </li>
        ))}
        {groups.size === 0 && (
          <li>
            <span className="muted">No usable evidence yet.</span>
          </li>
        )}
        {failed.length > 0 && (
          <li>
            <span className="coverage coverage-failed">
              {failed.length} failed collection{failed.length === 1 ? "" : "s"}
            </span>
          </li>
        )}
      </ul>
      {investigation.contradictions.length > 0 && (
        <div className="forge-contras">
          <h3 className="story-head">Contradictions</h3>
          <ul className="forge-contra-list">
            {investigation.contradictions.map((c) => (
              <li key={c.contradiction_id}>
                <p>{c.description}</p>
                <div className="forge-chip-row">
                  {c.evidence_ids.map((eid) => (
                    <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {onOpen && (
        <div className="controls">
          <button type="button" className="button button-ghost button-small" onClick={onOpen}>
            Open evidence
          </button>
        </div>
      )}
    </section>
  );
}
