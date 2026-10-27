import type { StatusResponse } from "../types";
import { RavenMark } from "./RavenMark";

export function Header({ status }: { status: StatusResponse | null }) {
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <RavenMark size={34} />
        </span>
        <div>
          <h1>FieldRook</h1>
          <p className="tagline">Diagnose. Verify. Resolve.</p>
        </div>
      </div>
      <div className="badges">
        {status ? (
          <>
            <span
              className={status.model_mode === "live" ? "badge badge-live" : "badge badge-sim"}
              title={
                status.model_mode === "live"
                  ? "Reasoning engine: live model (Meta Muse Spark)"
                  : "Reasoning engine: deterministic simulated analysis (no model calls)"
              }
            >
              {status.model_mode === "live" ? "LIVE MODEL" : "SIMULATED MODEL"}
            </span>
            <span
              className={
                status.live_diagnostics_available ? "badge badge-live" : "badge badge-sim"
              }
              title={
                status.live_diagnostics_available
                  ? "Host capability: this machine can run live read-only diagnostics"
                  : "Host capability: synthetic fixtures only on this machine"
              }
            >
              {status.live_diagnostics_available ? "LIVE DIAGNOSTICS" : "FIXTURES ONLY"}
            </span>
            <span className="badge">{status.model_name}</span>
          </>
        ) : (
          <span className="badge">connecting&hellip;</span>
        )}
      </div>
    </header>
  );
}
