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

/**
 * First-run welcome card (M025 GAMMA). Explains what FieldRook diagnoses,
 * what "local target" means, Collector packages, providers incl. live
 * local-AI status, when cloud calls need consent, and what works with no
 * model at all. Content mirrors docs/FIELD_KIT.md; honesty rules from
 * docs/M025_CONTRACTS.md apply (no small-model CPU-responsiveness claims,
 * local AI optional, cloud needs consent, offline stays useful).
 */
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
    <section
      className="card firstrun"
      data-testid="forge-first-run"
      aria-label="First-run guide"
    >
      <div className="card-head">
        <h2>
          <span className="eyebrow">Welcome to FieldRook</span>
        </h2>
        <span className="muted">first-run guide · dismiss any time</span>
      </div>

      <div className="firstrun-grid">
        <div>
          <h3 className="story-head">What FieldRook diagnoses</h3>
          <p>
            Evidence-backed diagnosis of Windows problems: a failing service
            (Settings → Standalone service diagnostics) or a symptom in your own
            words (Workbench intake). Diagnostics are read-only and bounded; the only
            thing FieldRook can ever change is its own demo worker, and only
            through propose → approve → execute with a single-use token.
          </p>
        </div>

        <div>
          <h3 className="story-head">What “local target” means</h3>
          <p>
            The <em>local target</em> is this machine: live diagnostics run
            here via PowerShell and describe this computer only. The header
            badge says <span className="badge badge-live">LIVE DIAGNOSTICS</span>{" "}
            when this host can do that, or{" "}
            <span className="badge badge-sim">FIXTURES ONLY</span> when it
            cannot. Anything about a <em>different</em> computer arrives as a
            Collector package — never by reaching across the network.
          </p>
        </div>

        <div>
          <h3 className="story-head">Collector packages</h3>
          <p>
            The Collector runs on the affected computer, shows a per-category
            consent screen, and writes a signed .zip package only after the
            technician acknowledges it. Attach the package at intake or import
            it mid-investigation with the sharing-consent box checked.
            Packages are validated atomically — any failure rejects the whole
            import — and nothing imported is ever executed. Imported evidence
            cannot be re-checked from here; collect a fresh package instead.
          </p>
        </div>

        <div>
          <h3 className="story-head">AI providers, live status</h3>
          <p>
            Inference provider (where intelligence runs) is separate from
            diagnostic target (which computer the evidence describes).
          </p>
          <ProviderStatusBlock status={providers} />
          <p className="muted">
            Local AI is optional: nothing is downloaded automatically, and the
            connection test runs only when you trigger it. Local speed
            depends on your hardware and model — measured true-CPU triage
            for the default profile is tens of seconds (see
            docs/PROVIDERS.md); no interactivity is promised.
          </p>
        </div>

        <div>
          <h3 className="story-head">When the cloud needs your consent</h3>
          <p>
            Nothing leaves localhost except explicit live-model calls, which
            carry only the current redacted investigation context. Screenshots
            require the sharing-consent box and are never stored — only
            metadata is kept. Switching an investigation to the Meta cloud
            provider while it holds evidence, notes, or screenshots needs an
            explicit confirmation, because that content would be transmitted
            on the next model round.
          </p>
        </div>

        <div>
          <h3 className="story-head">What works with no model</h3>
          <p>
            Everything except live reasoning: read-only diagnostics, evidence
            collection, deterministic simulated analysis (honestly labeled{" "}
            <span className="badge badge-sim">SIMULATED MODEL</span>), the
            knowledge library, Collector import and validation, technician
            plans, fix verification, and report export. Offline stays useful.
          </p>
        </div>
      </div>

      <div className="controls firstrun-actions">
        <button type="button" className="button" onClick={onStart}>
          Start diagnosing
        </button>
        <button type="button" className="button button-ghost" onClick={onDismiss}>
          Dismiss for now
        </button>
        <button
          type="button"
          className="button button-ghost firstrun-reset"
          onClick={onReset}
          title="Forget the dismissal so this guide opens on the next visit"
        >
          Show on next visit
        </button>
      </div>
    </section>
  );
}

function ProviderStatusBlock({ status }: { status: ProviderStatus }) {
  if (status.state === "loading") {
    return <p className="muted">Checking provider status…</p>;
  }
  if (status.state === "unavailable") {
    return (
      <p className="warn">
        Provider status is unavailable (the backend did not answer). Simulated
        offline analysis still works once the backend is up.
      </p>
    );
  }
  return (
    <ul className="firstrun-providers">
      {status.providers.map((p) => (
        <li key={p.name}>
          <span
            className={p.available ? "badge badge-live" : "badge badge-sim"}
            title={p.reason}
          >
            {p.name}: {p.available ? "ready" : "not configured"}
          </span>{" "}
          <span className="muted">
            {p.model} · {p.processing_location}
            {p.name === "local" && !p.available
              ? " · optional, nothing auto-downloads"
              : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
