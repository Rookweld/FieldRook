import type { InvestigationResponse } from "../types";
import { EvidenceChip } from "./EvidenceChip";

export function ProgressPanel({
  investigation,
  onEvidenceClick,
  onReverify,
  busy,
}: {
  investigation: InvestigationResponse;
  onEvidenceClick?: (id: string) => void;
  onReverify?: (evidenceId: string) => void;
  busy: boolean;
}) {
  const usable = investigation.evidence.filter((e) => !e.error).length;
  const failed = investigation.evidence.filter((e) => e.error).length;
  const budgetPct =
    investigation.tool_calls_max > 0
      ? Math.min(100, (investigation.tool_calls_used / investigation.tool_calls_max) * 100)
      : 0;
  // Open questions are the missing-evidence needs (short, actionable). The
  // longer uncertainty notes live in Diagnosis; repeating them here would
  // duplicate the page, so they are counted with a pointer instead.
  const needs = (investigation.assessment?.missing_evidence ?? []).slice(0, 6);
  const uncertaintyCount = investigation.assessment?.uncertainties.length ?? 0;
  const budgetLeft = investigation.tool_calls_max - investigation.tool_calls_used;

  return (
    <section className="card">
      <div className="card-head">
        <h2>Investigation progress</h2>
        <span className="muted">
          {usable} usable &middot; {failed} failed &middot; {investigation.refreshes.length} re-check
          {investigation.refreshes.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="budget-row">
        <span className="muted">
          Tool budget: {investigation.tool_calls_used} / {investigation.tool_calls_max} calls used
        </span>
        <div className="budget-bar" role="progressbar" aria-valuenow={investigation.tool_calls_used} aria-valuemax={investigation.tool_calls_max}>
          <div className="budget-fill" style={{ width: `${budgetPct}%` }} />
        </div>
      </div>

      {investigation.contradictions.length > 0 && (
        <div className="contradictions">
          <h3>Contradictions ({investigation.contradictions.length})</h3>
          {investigation.contradictions.map((hit) => (
            <p key={hit.contradiction_id} className="contradiction">
              <span className="tag tag-unv">CONFLICT</span> <span>{hit.description}</span>{" "}
              {hit.evidence_ids.map((eid) => (
                <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
              ))}
            </p>
          ))}
        </div>
      )}

      <h3>Unresolved questions</h3>
      {needs.length === 0 && uncertaintyCount === 0 && (
        <p className="muted">No open questions recorded.</p>
      )}
      {uncertaintyCount > 0 && (
        <p className="muted">
          {uncertaintyCount} open uncertaint{uncertaintyCount === 1 ? "y" : "ies"} — see
          Diagnosis below.
        </p>
      )}
      <ul className="unverified">
        {needs.map((text, i) => (
          <li key={i}>
            <span className="tag tag-unv">MISSING</span> <span>{text}</span>
          </li>
        ))}
      </ul>

      <h3>Suggested next checks</h3>
      {investigation.suggested_rechecks.length === 0 && (
        <p className="muted">
          {budgetLeft > 0
            ? "No re-checks suggested — current evidence is fresh and consistent."
            : "Tool budget exhausted — continuing from existing evidence only."}
        </p>
      )}
      <ul className="rechecks">
        {investigation.suggested_rechecks.map((s) => (
          <li key={s.evidence_id} className="recheck">
            <div className="cause-head">
              <EvidenceChip id={s.evidence_id} onSelect={onEvidenceClick} />
              <code className="mono muted">{s.tool_name}</code>
              {onReverify && (
                <button
                  type="button"
                  className="button button-small"
                  disabled={busy || budgetLeft <= 0}
                  onClick={() => onReverify(s.evidence_id)}
                >
                  Re-check now
                </button>
              )}
            </div>
            <p>{s.reason}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
