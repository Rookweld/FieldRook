import type { AnalysisResult } from "../types";
import { EvidenceChip } from "./EvidenceChip";

const GUIDANCE_IMPACT_CLASS: Record<string, string> = {
  SYSTEM_CHANGE: "system-change",
  PRIVILEGED_ACTION: "privileged-action",
  POTENTIALLY_DISRUPTIVE: "potentially-disruptive",
  UNSUPPORTED_OR_UNSAFE: "unsupported-or-unsafe",
};

export function DiagnosisPanel({
  analysis,
  warnings,
  onEvidenceClick,
}: {
  analysis: AnalysisResult;
  incidentId: string;
  createdAt: string;
  warnings: string[];
  onEvidenceClick?: (id: string) => void;
}) {
  const a = analysis;
  return (
    <section className="card">
      <div className="card-head">
        <h2>Diagnosis</h2>
        <span className={a.mode === "live" ? "badge badge-live" : "badge badge-sim"}>
          {a.mode === "live" ? "LIVE MODEL" : "SIMULATED"} &middot; {a.model}
        </span>
      </div>
      {warnings.map((w, i) => (
        <p key={i} className="warn">
          {w}
        </p>
      ))}
      <p className="summary">{a.summary}</p>

      <div className="legend">
        <span>
          <span className="tag tag-obs">OBSERVED</span> measured on the system
        </span>
        <span>
          <span className="tag tag-inf">INFERRED</span> AI hypothesis
        </span>
        <span>
          <span className="tag tag-unv">UNVERIFIED</span> unknown or missing
        </span>
      </div>

      <h3>Observed facts</h3>
      {a.facts.length === 0 && <p className="muted">No facts recorded.</p>}
      <ul className="facts">
        {a.facts.map((f, i) => (
          <li key={i}>
            <span className="tag tag-obs">OBSERVED</span> <span>{f.statement}</span>{" "}
            {f.evidence_ids.map((eid) => (
              <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
            ))}
          </li>
        ))}
      </ul>

      <h3>Possible root causes</h3>
      {a.causes.length === 0 && <p className="muted">No causes proposed.</p>}
      <ul className="causes">
        {a.causes.map((c, i) => (
          <li key={i}>
            <div className="cause-head">
              <span className="tag tag-inf">INFERRED</span>
              <strong>{c.title}</strong>
              <span className="likelihood">{c.likelihood}</span>
              {c.evidence_ids.map((eid) => (
                <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
              ))}
            </div>
            <p>{c.description}</p>
          </li>
        ))}
      </ul>

      <h3>Unresolved questions</h3>
      <ul className="unverified">
        {a.uncertainties.map((u, i) => (
          <li key={`u${i}`}>
            <span className="tag tag-unv">UNVERIFIED</span> <span>{u}</span>
          </li>
        ))}
        {a.missing_evidence.map((m, i) => (
          <li key={`m${i}`}>
            <span className="tag tag-unv">MISSING</span> <span>{m}</span>
          </li>
        ))}
      </ul>

      <h3>Technician next steps</h3>
      <p className="muted">
        <span className="tag tag-inf">INFERRED</span> Manual guidance — verify
        before acting. FieldRook executes nothing on this list.
      </p>
      {(a.next_steps ?? []).length > 0 ? (
        <div className="runbook">
          {(a.next_steps ?? []).map((s, i) => (
            <details key={i} className="runbook-step">
              <summary>
                <strong>{s.step}</strong>{" "}
                <span className={`impact impact-${s.impact}`}>{s.impact}</span>
                {s.admin_maybe && <span className="impact impact-admin">may need admin</span>}{" "}
                {s.guidance_impact && GUIDANCE_IMPACT_CLASS[s.guidance_impact] && (
                  <span className={`impact impact-${GUIDANCE_IMPACT_CLASS[s.guidance_impact]}`}>
                    {s.guidance_impact.toLowerCase().replace(/_/g, " ")}
                  </span>
                )}{" "}
                {s.evidence_ids.map((eid) => (
                  <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
                ))}
              </summary>
              {s.why && (
                <p>
                  <span className="runbook-label">Why:</span> {s.why}
                </p>
              )}
              {s.inspect && (
                <p>
                  <span className="runbook-label">Inspect:</span> {s.inspect}
                </p>
              )}
              {s.confirms && (
                <p>
                  <span className="runbook-label">Confirms / weakens:</span> {s.confirms}
                </p>
              )}
              {s.safety_note && (
                <p
                  className={
                    s.guidance_impact === "UNSUPPORTED_OR_UNSAFE" ||
                    s.guidance_impact === "POTENTIALLY_DISRUPTIVE"
                      ? "warn"
                      : undefined
                  }
                >
                  <span className="runbook-label">Safety:</span> {s.safety_note}
                </p>
              )}
            </details>
          ))}
        </div>
      ) : (
        <ol className="actions">
          {a.next_actions.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ol>
      )}

      <h3>Explanation</h3>
      <p>{a.explanation}</p>

      {a.validation_warnings.map((w, i) => (
        <p key={i} className="warn">
          {w}
        </p>
      ))}
    </section>
  );
}
