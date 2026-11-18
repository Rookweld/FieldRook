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
  const [supportCopied, setSupportCopied] = useState(false);
  const [supportError, setSupportError] = useState<string | null>(null);

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

  async function copySupportSummary(): Promise<void> {
    setSupportCopied(false);
    setSupportError(null);
    // Only product/runtime metadata. Never include evidence, host identity,
    // server logs, API keys, path names or technician notes in clipboard copy.
    const summary = [
      "FieldRook — support diagnostics",
      `Backend: ${status ? "connected" : "not connected"}`,
      `Backend version: ${status?.version ?? "unavailable"}`,
      `Service identity: ${status?.service ?? "unavailable"}`,
      `Platform: ${status?.platform ?? "unavailable"}`,
      `Reasoning: ${status?.model_mode ?? "unavailable"}`,
      `Diagnostics: ${status?.live_diagnostics_available ? "read-only live tools available" : "fixture-only or disconnected"}`,
      `Desktop shell: ${shellVersion ?? "not detected"}`,
      "Evidence, notes, credentials and logs are intentionally excluded.",
    ].join("\n");
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard access is unavailable in this window.");
      }
      await navigator.clipboard.writeText(summary);
      setSupportCopied(true);
    } catch (error) {
      setSupportError(error instanceof Error ? error.message : String(error));
    }
  }

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
        <div className="sf-utility-card sf-support">
          <h2>Support &amp; troubleshooting</h2>
          <p>
            If the service is unavailable, FieldRook checks again automatically.
            Restart the Windows desktop app if it cannot recover.
          </p>
          <p>
            Desktop diagnostic logs are stored locally under{" "}
            <code>%LOCALAPPDATA%\FieldRook\logs</code>.
            The native error screen also has an Open logs shortcut.
          </p>
          <button className="sf-btn sf-btn-dark sf-btn-sm" type="button"
            onClick={() => void copySupportSummary()}>
            Copy safe support summary
          </button>
          {supportCopied && (
            <p className="sf-support-ok" role="status">
              Support summary copied. No case content, secrets or logs were included.
            </p>
          )}
          {supportError && <p className="sf-support-error" role="alert">Copy failed: {supportError}</p>}
        </div>
        <details className="sf-utility-card sf-advanced-tools">
          <summary>Advanced tools · standalone service inspection</summary>
          <p>
            Inspect a Windows service without creating a case. This is an advanced
            diagnostic surface, not part of the normal case workflow.
          </p>
          <ServiceWorkstation />
        </details>
        <div className="sf-utility-card">
          <h2>About</h2>
          <p>FieldRook by ROOKWELD. A technician-first workspace for evidence-led investigations.</p>
        </div>
      </div>
    </section>
  );
}
