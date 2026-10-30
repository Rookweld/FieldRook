import { useEffect, useState } from "react";
import { ServiceWorkstation } from "../../components/ServiceWorkstation";
import type { SettingsViewProps } from "../types";
import { MotionSwitcher } from "../motion";
import { shellGetVersion } from "../shellBridge";
import "./Utility.css";

export function SettingsView({ status, investigation }: SettingsViewProps) {
  const prefersReduced =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [shellVersion, setShellVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    shellGetVersion().then(
      (v) => {
        if (!cancelled) setShellVersion(v.version);
      },
      () => {
        if (!cancelled) setShellVersion(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

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
              <dt>Desktop shell</dt>
              <dd>{shellVersion ?? "No desktop shell detected"}</dd>
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
          <MotionSwitcher label="Ambient motion" idPrefix="sf-settings-motion" />
          <p>
            Alive plays the full ambient instrument; Quiet dims and slows it; Off stops all
            decorative motion. The choice persists on this machine
            {prefersReduced ? ", and this system currently prefers reduced motion" : ""}.
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
