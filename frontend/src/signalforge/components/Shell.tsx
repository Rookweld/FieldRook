import { useEffect, useRef, type ReactNode } from "react";
import type { InvestigationResponse, StatusResponse } from "../../types";
import type { ShellProps, SignalView } from "../types";
import { CircuitVeins } from "../motion";
import { FieldKitDock } from "../dock/FieldKitDock";
import { useDockState } from "../dock/useDockState";
import "../signalforge.css";

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

/** Use an open case's actual inference provenance, not the global default. */
function ModeBadges({
  status,
  investigation,
}: {
  status: StatusResponse | null;
  investigation: InvestigationResponse | null;
}) {
  if (!status) {
    return <span className="sf-badge sf-badge-sim" role="status">Service unavailable</span>;
  }
  if (investigation) {
    const live = investigation.analysis_mode === "live";
    const engine = live
      ? (investigation.model.startsWith("local/") ? "Local AI" : "Live AI")
      : "Simulated analysis";
    const evidence = investigation.uses_fixtures
      ? "fixture data"
      : investigation.evidence.length + " evidence records";
    return (
      <span
        className={live ? "sf-badge sf-badge-live" : "sf-badge sf-badge-sim"}
        title={"This case used " + investigation.model + " (" + investigation.analysis_mode + "); " +
          evidence + ". Case history does not prove the model is connected now."}
        role="status"
      >
        Case: {engine} · {evidence}
      </span>
    );
  }
  const live = status.model_mode === "live";
  return (
    <span
      className={live ? "sf-badge sf-badge-live" : "sf-badge sf-badge-sim"}
      title={"Default: " + status.model_name + " (" + status.model_mode +
        "). A particular investigation may use a different inference provider."}
      role="status"
    >
      Default: {live ? "Live AI" : "Simulation"} · {status.live_diagnostics_available ? "local tools" : "demo data"}
    </span>
  );
}

const NAV_ITEMS: { view: SignalView; label: string; glyph: string }[] = [
  { view: "launchpad", label: "Launchpad", glyph: "⌂" },
  { view: "workbench", label: "Workbench", glyph: "↗" },
  { view: "evidence", label: "Evidence", glyph: "◈" },
  { view: "network", label: "Network Lab", glyph: "◍" },
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
    case "network":
      return "FIELDROOK / NETWORK LAB";
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
  // M028.A FIELD KIT dock owns the right rail. Visibility only swaps the
  // rail; the investigation engine (children) is never remounted, so case
  // state survives every dock action.
  const dock = useDockState();
  const { visibility, setVisibility, toggleOpen } = dock;
  const toggleRef = useRef<HTMLButtonElement>(null);
  const dockOpen = visibility === "open";

  useEffect(() => {
    if (visibility === "closed") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // Overlay parity with M026: at narrow widths Escape always
      // dismisses the rail; at wide widths only when focus is inside
      // the dock, so engine inputs keep their own Escape behavior.
      const target = event.target as HTMLElement | null;
      const inDock = target?.closest?.("#sf-fieldkit-dock") != null;
      const overlay = window.innerWidth <= 1180;
      if (!inDock && !overlay) return;
      setVisibility("closed");
      toggleRef.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visibility, setVisibility]);

  // Closing from inside the dock returns focus to the always-visible
  // main-column toggle, which is also the reopen control.
  const closeDock = () => {
    setVisibility("closed");
    window.setTimeout(() => toggleRef.current?.focus(), 0);
  };

  const handleVisibility: typeof setVisibility = (next) => {
    if (next === "closed") closeDock();
    else setVisibility(next);
  };

  const statusLine = status
    ? status.service + " · v" + status.version + " · " + (investigation
      ? "case " + investigation.model + " (" + investigation.analysis_mode + ")"
      : "default " + status.model_name + " (" + status.model_mode + ")")
    : "Service unavailable — case results may be historical";

  const bodyClass =
    visibility === "collapsed"
      ? "sf-body sf-dock-collapsed"
      : visibility === "closed"
        ? "sf-body sf-dock-closed"
        : "sf-body";

  return (
    <div className="sf-stage">
      <a className="sf-skip" href="#sf-main">
        Skip to main content
      </a>
      <div className="sf-veins-slot" data-motion-slot="circuit-veins" aria-hidden="true">
        <CircuitVeins />
      </div>
      <div className="app sf-app">
        <header className="sf-topbar">
          <div className="sf-mark" aria-hidden="true">
            R
          </div>
          <div className="sf-logo">
            Field<span>Rook</span>
          </div>
          <span className="sf-top-meta">Diagnose · Verify · Resolve</span>
          <div className="sf-top-spacer" />
          <div className="sf-badges">
            <ModeBadges status={status} investigation={investigation} />
          </div>
        </header>
        <div className={bodyClass}>
          <nav className="sf-nav" aria-label="Primary">
            <div className="sf-nav-head">
              <div className="sf-eyebrow">WORKSPACE</div>
              <p>Cases, evidence and tools</p>
            </div>
            <div className="sf-rail-nav">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.view}
                  type="button"
                  className={view === item.view ? "sf-navbtn sf-active" : "sf-navbtn"}
                  aria-label={item.label}
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
              <div className="sf-nav-bottom-label">
                BUILT BY ROOKWELD
                <br />
                <strong>FORGE. BUILD. IMAGINE.</strong>
              </div>
            </div>
          </nav>
          <main className="sf-main" id="sf-main" tabIndex={-1}>
            <div className="sf-ribbon">
              <span>{ribbonText(view, investigation !== null)}</span>
              <span className="sf-ribbon-pill">
                {investigation ? "CASE OPEN" : "READY FOR A CASE"}
              </span>
            </div>
            <button
              ref={toggleRef}
              type="button"
              data-testid="fieldkit-toggle"
              className="sf-rail-toggle"
              aria-expanded={visibility === "open"}
              aria-controls="sf-fieldkit-dock"
              onClick={toggleOpen}
            >
              {visibility === "open" ? "Hide Field Kit ✕" : "Open Field Kit ◈"}
            </button>
            {children}
          </main>
          <aside
            className={dockOpen ? "sf-rail sf-rail-dock sf-rail-open" : "sf-rail sf-rail-dock"}
            id="sf-fieldkit-dock"
            aria-label="Field Kit instrument dock"
          >
            <FieldKitDock
              view={view}
              investigation={investigation}
              visibility={visibility}
              activeId={dock.activeId}
              pins={dock.pins}
              pinNotice={dock.pinNotice}
              selectedEvidenceId={dock.selectedEvidenceId}
              onVisibility={handleVisibility}
              onActivate={dock.activate}
              onTogglePin={dock.togglePin}
              onSelectEvidence={dock.selectEvidence}
              onGoEvidence={onGoEvidence}
              onGoWorkbench={onGoWorkbench}
            />
          </aside>
        </div>
        <footer className="sf-status">
          <span>
            <span className="sf-demo-dot" aria-hidden="true" />
            <strong>FieldRook</strong>
          </span>
          <span className="sf-sep" aria-hidden="true" />
          <span className="sf-truncate">{statusLine}</span>
          <span className="sf-grow" />
          <span className="sf-sep" aria-hidden="true" />
          <span>ROOKWELD</span>
        </footer>
      </div>
    </div>
  );
}
