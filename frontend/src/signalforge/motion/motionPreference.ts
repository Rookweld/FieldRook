import { useSyncExternalStore } from "react";

/** Motion intensity. `alive` is full motion, `quiet` damps it, `off` kills decor. */
export type MotionMode = "alive" | "quiet" | "off";

/** Focus context. `work` marks a work-heavy view for ambient auto-damp. */
export type FocusContext = "default" | "work";

/** localStorage key for the persisted motion preference (M026 §4). */
export const MOTION_STORAGE_KEY = "fieldrook.motion.v1";

/**
 * Prototype value mapping. The Motion Lab used `ambient|quiet|off` for
 * `body[data-motion]`; the product key uses `alive|quiet|off` where
 * `alive` is the renamed `ambient`. Legacy stored `ambient` values map
 * to `alive` so early adopters keep full motion.
 */
export function parseMotionMode(raw: string | null | undefined): MotionMode | null {
  if (raw === "alive" || raw === "quiet" || raw === "off") return raw;
  if (raw === "ambient") return "alive";
  return null;
}

function readStoredMode(): MotionMode | null {
  try {
    return parseMotionMode(window.localStorage.getItem(MOTION_STORAGE_KEY));
  } catch {
    return null;
  }
}

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

/**
 * Resolve the initial mode: stored preference wins, else
 * `prefers-reduced-motion` defaults to `off`, else `alive`.
 */
export function resolveInitialMode(): MotionMode {
  return readStoredMode() ?? (prefersReducedMotion() ? "off" : "alive");
}

type MotionListener = (mode: MotionMode) => void;

const listeners = new Set<MotionListener>();
let currentMode: MotionMode | null = null;

function notify(mode: MotionMode): void {
  for (const fn of listeners) fn(mode);
}

/** Apply a mode: set `body[data-motion]`, persist, notify subscribers. */
export function applyMotionMode(mode: MotionMode): void {
  currentMode = mode;
  document.body.dataset.motion = mode;
  try {
    window.localStorage.setItem(MOTION_STORAGE_KEY, mode);
  } catch {
    /* private mode etc: the live switch still works, persistence is best-effort */
  }
  notify(mode);
}

/**
 * One-time init for main.tsx: resolve and apply the initial mode before
 * first paint. Idempotent.
 */
export function initMotionPreference(): MotionMode {
  if (currentMode) {
    document.body.dataset.motion = currentMode;
    return currentMode;
  }
  const mode = resolveInitialMode();
  currentMode = mode;
  document.body.dataset.motion = mode;
  return mode;
}

function subscribe(fn: MotionListener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

function getSnapshot(): MotionMode {
  if (!currentMode) currentMode = resolveInitialMode();
  return currentMode;
}

function getServerSnapshot(): MotionMode {
  return "alive";
}

/** React binding for the motion mode (switcher UI state). */
export function useMotionMode(): MotionMode {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/**
 * Mark the current view work-heavy (sustained troubleshooting) so ambient
 * decor auto-damps via `body[data-focus="work"]`. Pass false (or omit) on
 * unmount to restore. Views own calling this; motion owns the styling.
 */
export function setWorkHeavy(damp: boolean): void {
  if (damp) {
    document.body.dataset.focus = "work";
  } else {
    delete document.body.dataset.focus;
  }
}
