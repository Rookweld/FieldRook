import { useCallback, useState } from "react";

export type SignalforgeView = "launchpad" | "workbench" | "evidence" | "knowledge" | "settings";

export interface SignalforgeViewState {
  view: SignalforgeView;
  investigationId: string | null;
}

const STORAGE_KEY = "signalforge.view.v1";

const VIEWS: readonly SignalforgeView[] = ["launchpad", "workbench", "evidence", "knowledge", "settings"];

function isView(value: unknown): value is SignalforgeView {
  return typeof value === "string" && (VIEWS as readonly string[]).includes(value);
}

function loadInitial(): SignalforgeViewState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { view: "launchpad", investigationId: null };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return { view: "launchpad", investigationId: null };
    const record = parsed as Record<string, unknown>;
    return {
      view: isView(record.view) ? record.view : "launchpad",
      investigationId: typeof record.investigationId === "string" ? record.investigationId : null,
    };
  } catch {
    return { view: "launchpad", investigationId: null };
  }
}

/**
 * M026 navigation state (contract section 5). Replaces the M025 4-tab
 * model; seed/open/reset behaviour is preserved: reset() returns to a
 * fresh launchpad, which is also the error-boundary recovery target.
 * Persisted locally so a reload keeps the open case, never the answers.
 */
export function useViewState(): {
  state: SignalforgeViewState;
  go: (view: SignalforgeView) => void;
  openInvestigation: (id: string) => void;
  startNew: () => void;
  reset: () => void;
} {
  const [state, setState] = useState<SignalforgeViewState>(loadInitial);

  const store = useCallback((next: SignalforgeViewState) => {
    setState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* private mode: the view still works for this session */
    }
  }, []);

  const go = useCallback(
    (view: SignalforgeView) => {
      store({ view, investigationId: state.investigationId });
    },
    [state.investigationId, store],
  );

  const openInvestigation = useCallback(
    (id: string) => {
      store({ view: "workbench", investigationId: id });
    },
    [store],
  );

  const startNew = useCallback(() => {
    store({ view: "workbench", investigationId: null });
  }, [store]);

  const reset = useCallback(() => {
    store({ view: "launchpad", investigationId: null });
  }, [store]);

  return { state, go, openInvestigation, startNew, reset };
}
