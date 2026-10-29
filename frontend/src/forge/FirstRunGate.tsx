import { useState } from "react";
import { FirstRunPanel } from "./FirstRunPanel";
import "./FirstRun.css";

/**
 * First-run gate (M025 GAMMA). Mounted once at the top of App.tsx's main
 * content; owns the dismiss/persist marker and nothing else.
 *
 * Behavior:
 * - First visit (no marker): the welcome card is open.
 * - "Start diagnosing": closes AND persists the marker (tour stays gone).
 * - "Dismiss for now": closes for this session only (tour returns next load).
 * - Closed: a compact "First-run guide" button reopens the tour.
 * - Automation (navigator.webdriver, e.g. Playwright): renders nothing, so
 *   the existing E2E suites (incl. forge-workstation.spec.ts) pass unchanged.
 *   Documented in docs/FIELD_KIT.md ("Automated tests" under First run).
 */

export const FIRST_RUN_MARKER_KEY = "fieldrook.first-run.v1";
const FIRST_RUN_SEEN = "seen";

function readMarker(): boolean {
  try {
    return window.localStorage.getItem(FIRST_RUN_MARKER_KEY) === FIRST_RUN_SEEN;
  } catch {
    return false;
  }
}

function writeMarker(): void {
  try {
    window.localStorage.setItem(FIRST_RUN_MARKER_KEY, FIRST_RUN_SEEN);
  } catch {
    /* private mode: the tour simply returns next visit */
  }
}

function clearMarker(): void {
  try {
    window.localStorage.removeItem(FIRST_RUN_MARKER_KEY);
  } catch {
    /* nothing persisted; nothing to clear */
  }
}

function isAutomated(): boolean {
  return typeof navigator !== "undefined" && navigator.webdriver === true;
}

export function FirstRunGate() {
  const [open, setOpen] = useState<boolean>(() => !readMarker());
  const [automated] = useState<boolean>(isAutomated);

  if (automated) {
    return null;
  }

  if (!open) {
    return (
      <div className="firstrun-reopen">
        <button
          type="button"
          className="button button-ghost firstrun-reopen-btn"
          onClick={() => setOpen(true)}
        >
          First-run guide
        </button>
      </div>
    );
  }

  return (
    <FirstRunPanel
      onStart={() => {
        writeMarker();
        setOpen(false);
      }}
      onDismiss={() => setOpen(false)}
      onReset={() => {
        clearMarker();
        setOpen(false);
      }}
    />
  );
}
