import { useEffect, useState, type ReactNode } from "react";
import type { StatusResponse } from "../../types";
import { summarizeEvidence } from "../../evidenceSummary";
import type { EvidenceRailProps, ShellProps, SignalView } from "../types";
import "./signalforge.css";

/** Shared sun/rook/cliff instrument art. Colors resolve via CSS vars. */
export function RookFigure() {
  return (
    <div className="sf-sunscene" aria-hidden="true">
      <div className="sf-sun" />
      <div className="sf-sun-scan" />
      <svg className="sf-rook" viewBox="0 0 120 135">
        <path d="M26 115 L42 84 L38 60 Q40 32 63 23 Q77 11 91 20 L96 30 L119 39 L96 48 Q91 70 75 81 L81 115 L72 114 L63 88 L53 112 Z" />
        <path d="M42 55 Q15 39 8 18 Q48 17 67 42 Z" />
      </svg>
      <div className="sf-cliff" />
    </div>
  );
}

function ModeBadges({ status }: { status: StatusResponse | null }) {
  if (!status) {
    return (
      <>
        <span className="sf-badge">connecting&hellip;</span>
        <span
          className="sf-badge sf-badge-sim"
          data-motion-slot="motion-switch"
          title="Atmosphere controls arrive with the motion milestone; the interface follows the OS reduced-motion setting until then."
        >
          Atmosphere &middot; system
        </span>
      </>
    );
  }
  return (
    <>
      <span
        className={status.model_mode === "live" ? "sf-badge sf-badge-live" : "sf-badge sf-badge-sim"}
        title={
          status.model_mode === "live"
            ? `Reasoning engine: live model (${status.model_name || "unknown"})`
            : "Reasoning engine: deterministic simulated analysis (no model calls)"
        }
      >
        {status.model_mode === "live" ? "LIVE MODEL" : "SIMULATED MODEL"}
      </span>
      <span
        className={
          status.live_diagnostics_available ? "sf-badge sf-badge-live" : "sf-badge sf-badge-sim"
        }
        title={
          status.live_diagnostics_available
            ? "Host capability: this machine can run live read-only diagnostics"
            : "Host capability: synthetic fixtures only on this machine"
        }
      >
        {status.live_diagnostics_available ? "LIVE DIAGNOSTICS" : "FIXTURES ONLY"}
      </span>
      <span className="sf-badge">{status.model_name}</span>
    </>
  );
}

const NAV_ITEMS: { view: SignalView; label: string; glyph: string }[] = [
  { view: "launchpad", label: "Launchpad", glyph: "⌂" },
  { view: "workbench", label: "Workbench", glyph: "↗" },
  { view: "evidence", label: "Evidence", glyph: "◈" },
  { view: "knowledge", label: "Knowledge", glyph: "▤" },
  { view: "settings", label: "Settings", glyph: "⚙" },
];

function ribbonText(view: SignalView, hasCase: boolean): string {
  switch (view) {
    case "launchpad":
      return "FIELDROOK / LAUNCHPAD";
    case "workbench":
      return hasCase ? "FIELD REPORT / ACTIVE INVESTIGATION" : "FIELD REPORT / NO ACTIVE CASE";
    case "evidence":
      return "FIELDROOK / EVIDENCE";
    case "knowledge":
      return "FIELDROOK / KNOWLEDGE";
    case "settings":
      return "FIELDROOK / SETTINGS";
    default: {
      const _exhaustive: never = view;
      return _exhaustive;
    }
  }
}

export function EvidenceRail({ investigation, onGoEvidence, onGoWorkbench }: EvidenceRailProps) {
  const evidence = investigation?.evidence ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const effectiveId = selectedId ?? evidence[0]?.id ?? null;
  const selected = evidence.find((item) => item.id === effectiveId) ?? null;
  const summary = selected ? summarizeEvidence(selected).slice(0, 3) : [];

  return (
    <>
      <div className="sf-rail-header">
        <div className="sf-small">PROVENANCE / CASE RECORDS</div>
        <h2>
          EVIDENCE<span>.</span>
        </h2>
        <div className="sf-sub">
          {investigation ? `${evidence.length} records on this case` : "No active investigation"}
        </div>
      </div>
      {evidence.length === 0 ? (
        <p className="sf-rail-empty">
          {investigation
            ? "No evidence collected yet. Diagnostic results and technician notes will appear here with their source."
            : "Open a case from the Launchpad or start one in the Workbench — collected evidence will appear here with its source."}
        </p>
      ) : (
        <div className="sf-ev-list" role="group" aria-label="Case evidence">
          {evidence.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === effectiveId ? "sf-evbtn sf-active" : "sf-evbtn"}
              aria-current={item.id === effectiveId ? "true" : undefined}
              onClick={() => setSelectedId(item.id)}
            >
              <span className="sf-ev-ic" aria-hidden="true">
                {item.error ? "!" : "◎"}
              </span>
              <span className="sf-evtxt">
                <strong>{item.tool_name ?? item.category}</strong>
                <small>
                  {item.source} &middot; {new Date(item.collected_at).toLocaleDateString()}
                </small>
              </span>
              <span className="sf-ev-status">{item.error ? "ERROR" : item.category}</span>
            </button>
          ))}
        </div>
      )}
      <div className="sf-wavebox" data-motion-slot="signal-trace">
        <div className="sf-section-label">INSTRUMENT / UI ACTIVITY ONLY</div>
        <h3>Quiet instrument.</h3>
        <p>
          This panel will carry an animated activity cue. It is <strong>not</strong> a live health
          or network measurement.
        </p>
        <svg className="sf-heartbeat" viewBox="0 0 280 62" preserveAspectRatio="none" aria-hidden="true">
          <path
            d="M0 38 H37 L44 35 L52 40 L59 38 L65 38 L70 23 L76 55 L83 5 L90 42 L97 38 H145 L153 33 L160 42 L166 38 H191 L197 24 L203 52 L210 16 L216 39 L225 38 H280"
            fill="none"
            style={{ stroke: "var(--line)", strokeWidth: 2 }}
          />
        </svg>
        <div className="sf-signal-label">◉ STATIC / PRE-MOTION</div>
      </div>
      <div className="sf-inspector" aria-live="polite">
        {selected ? (
          <>
            <div className="sf-badge-line">
              {selected.category} &middot; {selected.source}
            </div>
            <h4>{selected.tool_name ?? selected.id}</h4>
            {selected.error ? (
              <p>Collection failed: {selected.error}</p>
            ) : summary.length > 0 ? (
              summary.map((row) => (
                <p key={row.label}>
                  {row.label}: {row.value}
                </p>
              ))
            ) : (
              <p>Record held; open the full evidence view for raw detail.</p>
            )}
            <p>
              <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoEvidence}>
                Full evidence view ↗
              </button>
            </p>
          </>
        ) : (
          <>
            <div className="sf-badge-line">NO RECORD SELECTED</div>
            <h4>Nothing to inspect</h4>
            <p>
              <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoWorkbench}>
                Go to Workbench ↗
              </button>
            </p>
          </>
        )}
      </div>
    </>
  );
}

export type SignalFrameProps = ShellProps & {
  onGoEvidence: () => void;
  onGoWorkbench: () => void;
  children: ReactNode;
};

export function SignalFrame({
  view,
  status,
  investigation,
  onNavigate,
  onGoEvidence,
  onGoWorkbench,
  children,
}: SignalFrameProps) {
  const [railOpen, setRailOpen] = useState(false);

  useEffect(() => {
    if (!railOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setRailOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [railOpen]);

  const statusLine = status
    ? `${status.service} · v${status.version} · ${status.model_name} (${status.model_mode})`
    : "Waiting for the backend on this machine";

  return (
    <div className="sf-stage">
      {/* DELTA mounts the CircuitVeins ambient background here. */}
      <div className="sf-veins-slot" data-motion-slot="circuit-veins" aria-hidden="true" />
      <div className="app sf-app">
        <a className="sf-skip" href="#sf-main">
          Skip to main content
        </a>
        <header className="sf-topbar">
          <div className="sf-mark" aria-hidden="true">
            R
          </div>
          <div className="sf-logo">
            Field<span>Rook</span>
          </div>
          <span className="sf-top-meta">M026 &middot; Signalforge</span>
          <span className="sf-top-meta">Diagnose. Verify. Resolve.</span>
          <div className="sf-top-spacer" />
          <div className="sf-badges">
            <ModeBadges status={status} />
          </div>
        </header>
        <div className="sf-body">
          <nav className="sf-nav" aria-label="Primary">
            <div className="sf-nav-head">
              <div className="sf-eyebrow">R/W &middot; Tool Nº 01</div>
              <h2>
                FIELD
                <br />
                <strong>ROOK.</strong>
              </h2>
              <p>THE TECHNICIAN&apos;S INSTRUMENT</p>
            </div>
            <div className="sf-rail-nav">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.view}
                  type="button"
                  className={view === item.view ? "sf-navbtn sf-active" : "sf-navbtn"}
                  aria-current={view === item.view ? "page" : undefined}
                  onClick={() => onNavigate(item.view)}
                >
                  <span className="sf-ico" aria-hidden="true">
                    {item.glyph}
                  </span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
            <div className="sf-nav-foot">
              <div className="sf-stamp" aria-hidden="true">
                R.
              </div>
              <div className="sf-nav-bottom-label">
                ROOKWELD / SIGNALFORGE
                <br />
                FORGE. BUILD. IMAGINE.
                <br />
                <strong>● LOCAL DESKTOP UI</strong>
              </div>
            </div>
          </nav>
          <main className="sf-main" id="sf-main" tabIndex={-1}>
            <div className="sf-ribbon">
              <span>{ribbonText(view, investigation !== null)}</span>
              <span className="sf-ribbon-pill">
                {status
                  ? status.live_diagnostics_available
                    ? "LIVE DIAGNOSTICS"
                    : "FIXTURES ONLY"
                  : "CONNECTING"}
              </span>
            </div>
            <button
              type="button"
              className="sf-rail-toggle"
              aria-expanded={railOpen}
              aria-controls="sf-evidence-rail"
              onClick={() => setRailOpen((open) => !open)}
            >
              {railOpen ? "Close evidence inspector ✕" : "Open evidence inspector ◈"}
            </button>
            {children}
          </main>
          <aside
            className={railOpen ? "sf-rail sf-rail-open" : "sf-rail"}
            id="sf-evidence-rail"
            aria-label="Evidence and signal inspector"
          >
            <EvidenceRail
              investigation={investigation}
              onGoEvidence={onGoEvidence}
              onGoWorkbench={onGoWorkbench}
            />
          </aside>
        </div>
        <footer className="sf-status">
          <span>
            <span className="sf-demo-dot" aria-hidden="true" />
            <strong>FieldRook M026</strong>
          </span>
          <span className="sf-sep" aria-hidden="true" />
          <span className="sf-truncate">{statusLine}</span>
          <span className="sf-grow" />
          <span className="sf-sep" aria-hidden="true" />
          <span>SIGNALFORGE</span>
        </footer>
      </div>
    </div>
  );
}
