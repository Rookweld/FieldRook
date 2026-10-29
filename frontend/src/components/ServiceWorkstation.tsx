import { useCallback, useEffect, useState } from "react";
import { ApiError, analyzeIncident, getDiagnostics, listServices } from "../api";
import type { DiagnosticBundle, IncidentAssessment, ServiceSummary } from "../types";
import { DiagnosisPanel } from "./DiagnosisPanel";
import { EvidencePanel } from "./EvidencePanel";
import { ProgressSteps, type Phase } from "./ProgressSteps";

export function ServiceWorkstation() {
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [servicesMode, setServicesMode] = useState<string>("…");
  const [selected, setSelected] = useState<string>("");
  const [useFixtures, setUseFixtures] = useState<boolean>(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [diagnostics, setDiagnostics] = useState<DiagnosticBundle | null>(null);
  const [assessment, setAssessment] = useState<IncidentAssessment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;
    async function boot(): Promise<void> {
      try {
        const svc = await listServices();
        if (cancelled) return;
        setServices(svc.services);
        setServicesMode(svc.mode);
        const preferred = svc.services.some((s) => s.name === "wuauserv")
          ? "wuauserv"
          : (svc.services[0]?.name ?? "");
        setSelected(preferred);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, []);

  const busy = phase === "collecting" || phase === "analyzing";

  const investigate = useCallback(async (): Promise<void> => {
    if (!selected || busy) return;
    setError(null);
    setAssessment(null);
    setDiagnostics(null);
    const flag = useFixtures ? true : undefined;
    try {
      setPhase("collecting");
      const diag = await getDiagnostics(selected, flag);
      setDiagnostics(diag);
      setPhase("analyzing");
      const result = await analyzeIncident(selected, flag);
      setAssessment(result);
      setPhase("done");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Request failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
      setPhase("idle");
    }
  }, [selected, useFixtures, busy]);

  const bundle = assessment?.diagnostics ?? diagnostics;

  return (
    <>
      {error && (
        <div className="card error" role="alert">
          <div>
            <strong>Error.</strong> <span>{error}</span>
          </div>
          <p className="hint">
            Is the FieldRook desktop backend running on this machine? See the
            Field Kit guide (docs/FIELD_KIT.md) for startup steps.
          </p>
        </div>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Service investigation</h2>
          <span className="muted">service list: {servicesMode}</span>
        </div>
        {loading ? (
          <p>Connecting to FieldRook backend…</p>
        ) : (
          <div className="controls">
            <label className="field">
              <span>Windows service</span>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                disabled={busy || services.length === 0}
              >
                {services.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.display_name} ({s.name}) — {s.status}
                  </option>
                ))}
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={useFixtures}
                onChange={(e) => setUseFixtures(e.target.checked)}
                disabled={busy}
              />
              <span>Force fixture data</span>
            </label>
            <button
              className="button"
              onClick={() => void investigate()}
              disabled={busy || !selected}
            >
              {busy ? "Investigating…" : "Investigate"}
            </button>
          </div>
        )}
        <ProgressSteps phase={phase} />
      </section>

      {bundle && <EvidencePanel bundle={bundle} />}
      {assessment && (
        <DiagnosisPanel
          analysis={assessment.analysis}
          incidentId={assessment.incident_id}
          createdAt={assessment.created_at}
          warnings={assessment.warnings}
        />
      )}
    </>
  );
}
