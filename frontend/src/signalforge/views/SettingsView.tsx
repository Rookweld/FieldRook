import { ServiceWorkstation } from "../../components/ServiceWorkstation";
import type { SettingsViewProps } from "../types";
import "./Utility.css";

export function SettingsView({ status, investigation }: SettingsViewProps) {
  const prefersReduced =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <section className="sf-screen" aria-label="Settings">
      <div className="sf-utility">
        <div className="sf-eyebrow">Instrument configuration</div>
        <h1>
          KNOW THE
          <br />
          INSTRUMENT.
        </h1>
        <p>
          Connection, reasoning, and atmosphere. Settings describe this machine and its backend —
          nothing here reaches across the network.
        </p>
        <div className="sf-utility-card">
          <h2>Backend connection</h2>
          {status ? (
            <dl className="sf-kv">
              <dt>Service</dt>
              <dd>{status.service}</dd>
              <dt>Version</dt>
              <dd>{status.version}</dd>
              <dt>Platform</dt>
              <dd>{status.platform}</dd>
              <dt>Reasoning</dt>
              <dd>
                {status.model_name} ({status.model_mode})
              </dd>
              <dt>Diagnostics</dt>
              <dd>
                {status.live_diagnostics_available
                  ? "Live read-only tools on this machine"
                  : "Synthetic fixtures only"}
              </dd>
            </dl>
          ) : (
            <p>Backend not reached yet — the workbench connects automatically once it answers.</p>
          )}
        </div>
        <div className="sf-utility-card">
          <h2>Providers</h2>
          <p>
            {investigation?.provider_info
              ? `Active case runs on ${investigation.provider_info.name} (${investigation.provider_info.model}); processing: ${investigation.provider_info.processing_location}.`
              : "No active case. Inference provider is chosen per investigation in the Workbench intake; cloud providers always need explicit consent."}
          </p>
        </div>
        <div className="sf-utility-card">
          <h2>Motion &amp; atmosphere</h2>
          <p>
            Ambient instrument motion (circuit pulses, activity trace) arrives with the motion
            milestone. Until then the interface is static, and the OS reduced-motion preference is
            always respected{prefersReduced ? " — this system currently prefers reduced motion" : ""}.
          </p>
        </div>
        <div className="sf-utility-card">
          <h2>Standalone service diagnostics</h2>
          <p>
            Service lookup, preserved: diagnose a Windows service directly, without opening a
            full investigation.
          </p>
          <ServiceWorkstation />
        </div>
        <div className="sf-utility-card">
          <h2>About</h2>
          <p>FieldRook M026 · SIGNALFORGE technician interface · local desktop UI.</p>
        </div>
      </div>
    </section>
  );
}
