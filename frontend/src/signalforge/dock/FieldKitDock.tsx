import { useEffect, useMemo, useRef } from "react";
import type { InvestigationResponse } from "../../types";
import type { SignalView } from "../types";
import { EvidencePanel } from "./EvidencePanel";
import {
  EVIDENCE_INSTRUMENT_ID,
  listInstruments,
  MAX_DOCK_PINS,
  type InstrumentDescriptor,
} from "./instruments";
import type { DockVisibility } from "./useDockState";
import "./fieldkit.css";

export type FieldKitDockProps = {
  view: SignalView;
  investigation: InvestigationResponse | null;
  visibility: DockVisibility;
  activeId: string;
  pins: string[];
  pinNotice: string | null;
  selectedEvidenceId: string | null;
  onVisibility: (next: DockVisibility) => void;
  onActivate: (id: string) => void;
  onTogglePin: (id: string) => void;
  onSelectEvidence: (id: string) => void;
  onGoEvidence: () => void;
  onGoWorkbench: () => void;
};

function tabLabel(instrument: InstrumentDescriptor): string {
  return instrument.status === "ready"
    ? instrument.title
    : `${instrument.title}, coming soon`;
}

function ComingSoonPanel({
  instrument,
  onBackToEvidence,
}: {
  instrument: InstrumentDescriptor;
  onBackToEvidence: () => void;
}) {
  return (
    <div className="sf-soonpanel">
      <div className="sf-eyebrow">FIELD KIT / UNAVAILABLE</div>
      <h3>
        <span aria-hidden="true">{instrument.glyph} </span>
        {instrument.title}
      </h3>
      <p>
        <span className="sf-badge">COMING SOON</span>
      </p>
      <p>{instrument.unavailableNote ?? `${instrument.title} is not available in this build.`}</p>
      <p>
        <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onBackToEvidence}>
          Back to Evidence ◈
        </button>
      </p>
    </div>
  );
}

/**
 * FIELD KIT instrument dock (M028.A). Expandable, restrained right-side
 * dock: open/close/collapse, tool switching, up to 3 pinned favorites.
 * The M026 evidence rail is preserved behind the Evidence tab; the dock
 * never remounts the investigation engine, so case state survives every
 * tool switch. Static CSS only — no animation, trivially reduced-motion
 * safe.
 */
export function FieldKitDock({
  view,
  investigation,
  visibility,
  activeId,
  pins,
  pinNotice,
  selectedEvidenceId,
  onVisibility,
  onActivate,
  onTogglePin,
  onSelectEvidence,
  onGoEvidence,
  onGoWorkbench,
}: FieldKitDockProps) {
  const instruments = useMemo(() => listInstruments(), []);
  const active = instruments.find((entry) => entry.id === activeId) ?? instruments[0];
  // NOTE: the switcher deliberately uses plain buttons (aria-current) and
  // a region, NOT the tablist/tab/tabpanel pattern: the investigation
  // engine already owns role="tab" on this page (M026 specs address the
  // engine's Evidence tab unscoped), and a second tabset would collide.
  const switcherRef = useRef<HTMLDivElement>(null);
  const collapseRef = useRef<HTMLButtonElement>(null);
  const expandRef = useRef<HTMLButtonElement>(null);
  const prevVisibility = useRef(visibility);

  // Focus follows collapse/expand so keyboard users never lose their
  // place. Compares against the previous value (StrictMode-safe: the
  // double-invoked mount effect sees no change and does nothing).
  useEffect(() => {
    if (prevVisibility.current === visibility) return;
    prevVisibility.current = visibility;
    if (visibility === "collapsed") expandRef.current?.focus();
    else if (visibility === "open") collapseRef.current?.focus();
  }, [visibility]);

  const moveSwitchFocus = (direction: 1 | -1) => {
    const tabs = [...(switcherRef.current?.querySelectorAll(".sf-dock-tab") ?? [])] as HTMLElement[];
    if (tabs.length === 0) return;
    const current = tabs.indexOf(document.activeElement as HTMLElement);
    const next = current < 0 ? 0 : (current + direction + tabs.length) % tabs.length;
    tabs[next]?.focus();
  };

  const onSwitcherKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      moveSwitchFocus(1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      moveSwitchFocus(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      const tabs = switcherRef.current?.querySelectorAll(".sf-dock-tab") as NodeListOf<HTMLElement> | undefined;
      tabs?.[0]?.focus();
    } else if (event.key === "End") {
      event.preventDefault();
      const tabs = switcherRef.current?.querySelectorAll(".sf-dock-tab") as NodeListOf<HTMLElement> | undefined;
      if (tabs && tabs.length > 0) tabs[tabs.length - 1]?.focus();
    }
  };

  if (visibility === "closed") return null;

  if (visibility === "collapsed") {
    return (
      <div className="sf-dockstrip" data-testid="fieldkit-strip" role="group" aria-label="Field Kit, collapsed">
        <button
          ref={expandRef}
          type="button"
          className="sf-stripbtn sf-strip-expand"
          aria-label="Expand Field Kit dock"
          onClick={() => onVisibility("open")}
        >
          <span aria-hidden="true">◈</span>
        </button>
        {instruments.map((instrument) => (
          <button
            key={instrument.id}
            type="button"
            className={
              instrument.id === active.id ? "sf-stripbtn sf-active" : "sf-stripbtn"
            }
            aria-label={`${tabLabel(instrument)}${pins.includes(instrument.id) ? " (pinned)" : ""}`}
            aria-current={instrument.id === active.id ? "true" : undefined}
            title={tabLabel(instrument)}
            onClick={() => {
              onActivate(instrument.id);
              onVisibility("open");
            }}
          >
            <span aria-hidden="true">{instrument.glyph}</span>
          </button>
        ))}
      </div>
    );
  }

  const pinned = pins
    .map((id) => instruments.find((entry) => entry.id === id))
    .filter((entry): entry is InstrumentDescriptor => entry !== undefined);

  return (
    <div className="sf-dock" data-testid="fieldkit-dock">
      <div className="sf-dock-head">
        <div className="sf-dock-title">
          <div className="sf-eyebrow">FIELD KIT / INSTRUMENTS</div>
          <h2>
            DOCK<span>.</span>
          </h2>
        </div>
        <div className="sf-dock-actions">
          <button
            ref={collapseRef}
            type="button"
            className="sf-dock-iconbtn sf-dock-collapse-btn"
            aria-label="Collapse Field Kit dock"
            title="Collapse to a tool strip"
            onClick={() => onVisibility("collapsed")}
          >
            <span aria-hidden="true">«</span>
          </button>
          <button
            type="button"
            className="sf-dock-iconbtn"
            aria-label="Close Field Kit dock"
            title="Close the dock"
            onClick={() => onVisibility("closed")}
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>
      </div>

      {pinned.length > 0 && (
        <div className="sf-dock-pinned" data-testid="fieldkit-pinned">
          <div className="sf-section-label">
            PINNED · {pinned.length}/{MAX_DOCK_PINS}
          </div>
          <div className="sf-pinrow" role="group" aria-label="Pinned instruments">
            {pinned.map((instrument) => (
              <button
                key={instrument.id}
                type="button"
                className={
                  instrument.id === active.id ? "sf-pinbtn sf-active" : "sf-pinbtn"
                }
                aria-current={instrument.id === active.id ? "true" : undefined}
                onClick={() => onActivate(instrument.id)}
              >
                <span aria-hidden="true">{instrument.glyph} </span>
                {instrument.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div
        ref={switcherRef}
        role="group"
        aria-label="Field Kit instruments"
        className="sf-dock-tabs"
        onKeyDown={onSwitcherKeyDown}
      >
        {instruments.map((instrument) => {
          const selected = instrument.id === active.id;
          const pinnedActive = pins.includes(instrument.id);
          const pinDisabled = !pinnedActive && pins.length >= MAX_DOCK_PINS;
          return (
            <div key={instrument.id} className="sf-dock-row">
              <button
                type="button"
                aria-current={selected ? "true" : undefined}
                aria-label={tabLabel(instrument)}
                className={
                  selected
                    ? "sf-dock-tab sf-active"
                    : instrument.status === "ready"
                      ? "sf-dock-tab"
                      : "sf-dock-tab sf-soon"
                }
                onClick={() => onActivate(instrument.id)}
              >
                <span className="sf-dock-glyph" aria-hidden="true">
                  {instrument.glyph}
                </span>
                <span className="sf-dock-tabtxt">
                  <strong>{instrument.title}</strong>
                  <small>{instrument.blurb}</small>
                </span>
                {instrument.status === "coming-soon" && (
                  <span className="sf-soon-tag">SOON</span>
                )}
              </button>
              <button
                type="button"
                className="sf-dock-pin"
                aria-label={`${pinnedActive ? "Unpin" : "Pin"} ${instrument.title}`}
                aria-pressed={pinnedActive}
                title={
                  pinnedActive
                    ? `Unpin ${instrument.title}`
                    : pinDisabled
                      ? `Pin limit reached (${MAX_DOCK_PINS} max) — unpin a favorite first`
                      : `Pin ${instrument.title} as a favorite`
                }
                disabled={pinDisabled}
                onClick={() => onTogglePin(instrument.id)}
              >
                <span aria-hidden="true">{pinnedActive ? "★" : "☆"}</span>
              </button>
            </div>
          );
        })}
      </div>

      <div className="sf-dock-status" aria-live="polite">
        {pinNotice ?? `${instruments.length} instruments · ${pins.length} pinned`}
      </div>

      <div
        role="region"
        aria-label={`${active.title} instrument`}
        className="sf-dock-panel"
        tabIndex={0}
      >
        {/* M028.B/C extension point: add `active.id === "evidence-lens"` /
            "network-lab" branches rendering the real panels here. Anything
            without a real panel keeps the honest ComingSoonPanel below. */}
        {active.id === EVIDENCE_INSTRUMENT_ID ? (
          <div className="sf-dock-evwrap">
            <EvidencePanel
              view={view}
              investigation={investigation}
              onGoEvidence={onGoEvidence}
              onGoWorkbench={onGoWorkbench}
              selectedId={selectedEvidenceId}
              onSelectEvidence={onSelectEvidence}
            />
          </div>
        ) : (
          <ComingSoonPanel
            instrument={active}
            onBackToEvidence={() => onActivate(EVIDENCE_INSTRUMENT_ID)}
          />
        )}
      </div>
    </div>
  );
}
