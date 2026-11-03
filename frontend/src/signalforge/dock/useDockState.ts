import { useCallback, useEffect, useState } from "react";
import {
  EVIDENCE_INSTRUMENT_ID,
  getInstrument,
  isKnownInstrument,
  MAX_DOCK_PINS,
} from "./instruments";

/** open = full panel; collapsed = slim tool strip; closed = hidden. */
export type DockVisibility = "open" | "collapsed" | "closed";

/**
 * Persisted dock prefs. UI preference only: instrument ids and pins.
 * Never case data, never evidence content, never secrets.
 */
const STORAGE_KEY = "fieldrook.dock.v1";

type DockPrefs = {
  activeId: string;
  pins: string[];
};

function loadPrefs(): DockPrefs {
  const fallback: DockPrefs = { activeId: EVIDENCE_INSTRUMENT_ID, pins: [] };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return fallback;
    const record = parsed as Record<string, unknown>;
    const pins = Array.isArray(record.pins)
      ? [...new Set(record.pins.filter((id): id is string => typeof id === "string"))]
          .filter((id) => isKnownInstrument(id))
          .slice(0, MAX_DOCK_PINS)
      : [];
    const activeId =
      typeof record.activeId === "string" && isKnownInstrument(record.activeId)
        ? record.activeId
        : EVIDENCE_INSTRUMENT_ID;
    return { activeId, pins };
  } catch {
    return fallback;
  }
}

/**
 * FIELD KIT dock state (M028.A). Owns visibility, the active instrument,
 * up to MAX_DOCK_PINS favorites, and the selected evidence id.
 *
 * Evidence selection lives here (not in the panel) so switching
 * instruments and returning loses neither the selection nor — since the
 * engine is never remounted by the dock — any case state.
 */
export function useDockState(): {
  visibility: DockVisibility;
  setVisibility: (next: DockVisibility) => void;
  toggleOpen: () => void;
  activeId: string;
  activate: (id: string) => void;
  pins: string[];
  togglePin: (id: string) => void;
  isPinned: (id: string) => boolean;
  pinsFull: boolean;
  pinNotice: string | null;
  selectedEvidenceId: string | null;
  selectEvidence: (id: string) => void;
} {
  const [prefs, setPrefs] = useState<DockPrefs>(loadPrefs);
  const [visibility, setVisibility] = useState<DockVisibility>("open");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [pinNotice, setPinNotice] = useState<string | null>(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      /* private mode: the dock still works for this session */
    }
  }, [prefs]);

  const toggleOpen = useCallback(() => {
    setVisibility((current) => (current === "closed" ? "open" : "closed"));
  }, []);

  const activate = useCallback(
    (id: string) => {
      if (!isKnownInstrument(id)) return;
      setPrefs((current) => ({ ...current, activeId: id }));
      setVisibility((current) => (current === "closed" ? "open" : current));
    },
    [],
  );

  const togglePin = useCallback(
    (id: string) => {
      const instrument = getInstrument(id);
      if (!instrument) return;
      if (prefs.pins.includes(id)) {
        setPinNotice(`Unpinned ${instrument.title}.`);
        setPrefs({ ...prefs, pins: prefs.pins.filter((pin) => pin !== id) });
        return;
      }
      if (prefs.pins.length >= MAX_DOCK_PINS) {
        setPinNotice(`Pin limit reached: unpin a favorite to add another (${MAX_DOCK_PINS} max).`);
        return;
      }
      const next = [...prefs.pins, id];
      setPinNotice(`Pinned ${instrument.title} (${next.length} of ${MAX_DOCK_PINS}).`);
      setPrefs({ ...prefs, pins: next });
    },
    [prefs],
  );

  const isPinned = useCallback((id: string) => prefs.pins.includes(id), [prefs.pins]);

  const selectEvidence = useCallback((id: string) => {
    setSelectedEvidenceId(id);
  }, []);

  return {
    visibility,
    setVisibility,
    toggleOpen,
    activeId: prefs.activeId,
    activate,
    pins: prefs.pins,
    togglePin,
    isPinned,
    pinsFull: prefs.pins.length >= MAX_DOCK_PINS,
    pinNotice,
    selectedEvidenceId,
    selectEvidence,
  };
}
