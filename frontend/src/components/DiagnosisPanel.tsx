import type { IncidentAssessment } from "../types";

export function DiagnosisPanel({ assessment }: { assessment: IncidentAssessment }) {
  const a = assessment.analysis;
  return (
    <section className="card">
      <div className="card-head">
        <h2>Diagnosis</h2>
        <span className={a.mode === "live" ? "badge badge-live" : "badge badge-sim"}>
          {a.mode === "live" ? "LIVE MODEL" : "SIMULATED"} &middot; {a.model}
        </span>
      </div>
      <p className="muted">
        Incident {assessment.incident_id} &middot;{" "}
        {new Date(assessment.created_at).toLocaleString()}
      </p>
      {assessment.warnings.map((w, i) => (
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
              <code key={eid} className="chip">
                {eid}
              </code>
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
                <code key={eid} className="chip">
                  {eid}
                </code>
              ))}
            </div>
            <p>{c.description}</p>
          </li>
        ))}
      </ul>

      <h3>Uncertainty and missing evidence</h3>
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

      <h3>Recommended next diagnostic steps</h3>
      <ol className="actions">
        {a.next_actions.map((n, i) => (
          <li key={i}>{n}</li>
        ))}
      </ol>

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
