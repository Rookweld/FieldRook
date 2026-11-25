import { useEffect, useState } from "react";
import { listProviders } from "../api";
import type { ProviderOption } from "../types";
import "./FirstRun.css";

export type FirstRunPanelProps = {
  onStart: () => void;
  onDismiss: () => void;
  onReset: () => void;
};

type ProviderStatus =
  | { state: "loading" }
  | { state: "ready"; providers: ProviderOption[] }
  | { state: "unavailable" };

/** A single short path to the first real case. Technical detail stays optional. */
export function FirstRunPanel({ onStart, onDismiss, onReset }: FirstRunPanelProps) {
  const [providers, setProviders] = useState<ProviderStatus>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;
    listProviders().then(
      (entries) => {
        if (!cancelled) setProviders({ state: "ready", providers: entries });
      },
      () => {
        if (!cancelled) setProviders({ state: "unavailable" });
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="card firstrun firstrun-simple" data-testid="forge-first-run" aria-label="First-run guide">
      <div className="firstrun-intro">
        <span className="eyebrow">WELCOME TO FIELDROOK</span>
        <h2>Bring a real Windows problem.</h2>
        <p>
          No setup wizard or fictional case required. Describe something that actually
          fails and follow one check at a time.
        </p>
      </div>

      <ol className="firstrun-steps" aria-label="Your first investigation in three steps">
        <li><strong>Describe the symptom</strong><span>What fails, and when?</span></li>
        <li><strong>Choose the computer</strong><span>This PC, or a different authorized PC.</span></li>
        <li><strong>Check and record</strong><span>Separate observations from guesses. Verify the result.</span></li>
      </ol>

      <p className="firstrun-safety">
        FieldRook never applies a fix automatically. Its local diagnostics inspect
        this computer only; describing another PC does not scan it remotely.
      </p>

      <details className="firstrun-more">
        <summary>How does AI and evidence collection work?</summary>
        <div className="firstrun-more-content">
          <p>
            A simulated analysis can organize a case without using a live AI model.
            It is labelled simulated and must not be treated as proof of a cause.
            Local AI is optional and needs a separately configured model server;
            nothing is downloaded automatically.
          </p>
          <ProviderStatusBlock status={providers} />
          <p>
            A provider marked configured is <strong>not</strong> confirmed reachable.
            Cloud AI, when configured and selected, can transmit redacted case context.
            Only share data you have permission to use. Screenshots require explicit consent.
          </p>
          <p>
            Read-only diagnostics can inspect this Windows PC; for a different
            computer, use technician observations or an authorized Collector package.
            Collector data is never executed as code. Review proposed changes
            yourself before taking action.
          </p>
        </div>
      </details>

      <div className="controls firstrun-actions">
        <button type="button" className="button" onClick={onStart}>
          Start my first investigation ↗
        </button>
        <button type="button" className="button button-ghost" onClick={onDismiss}>
          Not now
        </button>
        <button type="button" className="button button-ghost firstrun-reset" onClick={onReset}
          title="Show this guide automatically again on the next visit">
          Show next time
        </button>
      </div>
    </section>
  );
}

function ProviderStatusBlock({ status }: { status: ProviderStatus }) {
  if (status.state === "loading") {
    return <p className="muted">Reading configured providers…</p>;
  }
  if (status.state === "unavailable") {
    return <p className="warn">Provider configuration cannot be read until the backend responds.</p>;
  }
  return (
    <ul className="firstrun-providers">
      {status.providers.map((provider) => (
        <li key={provider.name}>
          <strong>{provider.name}</strong> — {provider.available ? "configured" : "not configured"}
          <span className="muted"> · {provider.processing_location}</span>
        </li>
      ))}
    </ul>
  );
}
