import type { EvidenceRefresh } from "../types";
import { EvidenceChip } from "./EvidenceChip";

const VERDICT_CLS: Record<EvidenceRefresh["verdict"], string> = {
  changed: "verdict-changed",
  unchanged: "verdict-unchanged",
  unavailable: "verdict-unavailable",
};

function fmt(when: string | null): string {
  if (!when) return "—";
  return new Date(when).toLocaleString();
}

export function RefreshPanel({
  refreshes,
  onEvidenceClick,
}: {
  refreshes: EvidenceRefresh[];
  onEvidenceClick?: (id: string) => void;
}) {
  if (refreshes.length === 0) return null;
  return (
    <section className="card">
      <div className="card-head">
        <h2>Evidence changes between rounds</h2>
        <span className="muted">
          {refreshes.length} re-check{refreshes.length === 1 ? "" : "s"} &middot; history preserved
        </span>
      </div>
      <ol className="refreshes">
        {refreshes.map((r, i) => (
          <li key={i} className="refresh">
            <div className="cause-head">
              <EvidenceChip id={r.old_evidence_id} onSelect={onEvidenceClick} />
              <span aria-hidden="true">→</span>
              {r.new_evidence_id ? (
                <EvidenceChip id={r.new_evidence_id} onSelect={onEvidenceClick} />
              ) : (
                <span className="muted">(collection failed)</span>
              )}
              <span className={`verdict ${VERDICT_CLS[r.verdict]}`}>{r.verdict.toUpperCase()}</span>
              <code className="mono muted">{r.tool_name}</code>
            </div>
            <p className="muted refresh-times">
              Historical: {fmt(r.old_collected_at)} &middot; Current: {fmt(r.new_collected_at)}{" "}
              &middot; Compared: {fmt(r.compared_at)}
            </p>
            {r.changes.length > 0 && (
              <ul className="refresh-changes">
                {r.changes.map((change, j) => (
                  <li key={j}>
                    <code className="mono">{change}</code>
                  </li>
                ))}
              </ul>
            )}
            {r.affected_causes.length > 0 && (
              <p className="warn">
                Hypotheses built on the old reading may need review:{" "}
                {r.affected_causes.join("; ")}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
