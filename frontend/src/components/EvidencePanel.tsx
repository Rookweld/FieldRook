import type { DiagnosticBundle } from "../types";

export function EvidencePanel({ bundle }: { bundle: DiagnosticBundle }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Evidence</h2>
        <span className={bundle.mode === "live" ? "badge badge-live" : "badge badge-sim"}>
          {bundle.mode === "live" ? "LIVE" : "FIXTURE"} &middot; {bundle.service_name}
        </span>
      </div>
      <p className="muted">
        Collected {new Date(bundle.collected_at).toLocaleString()} &middot;{" "}
        {bundle.items.length} items
      </p>
      {bundle.warnings.map((w, i) => (
        <p key={i} className="warn">
          {w}
        </p>
      ))}
      <div className="evidence-list">
        {bundle.items.map((item) => (
          <article key={item.id} className="evidence-item">
            <div className="evidence-head">
              <code className="chip">{item.id}</code>
              <strong>{item.category}</strong>
              <code className="mono muted">{item.source}</code>
            </div>
            {item.error ? (
              <p className="item-error">Collection error: {item.error}</p>
            ) : (
              <pre className="pre">{JSON.stringify(item.data, null, 2)}</pre>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
