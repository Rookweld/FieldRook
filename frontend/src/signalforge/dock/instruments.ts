/**
 * FIELD KIT instrument registry (M028.A).
 *
 * The dock renders one tab per descriptor. `ready` instruments render a
 * real panel; `coming-soon` instruments render an honest unavailable card
 * and must never masquerade as usable.
 *
 * Extension point for M028.B/C: call `registerInstrument()` at module
 * scope (before first render) with status "ready" and add the matching
 * panel entry in FieldKitDock's PANELS table. Unknown ids stored by older
 * builds are dropped by useDockState validation.
 */

export type InstrumentStatus = "ready" | "coming-soon";

export type InstrumentDescriptor = {
  /** Stable id. Persisted in pin prefs, so never rename. */
  id: string;
  /** Short tab label. */
  title: string;
  /** Text glyph from the SIGNALFORGE set (no emoji). */
  glyph: string;
  status: InstrumentStatus;
  /** One-line honest description shown on the tab row. */
  blurb: string;
  /** Required when status is "coming-soon": shown on the unavailable card. */
  unavailableNote?: string;
};

/** The preserved M026 evidence rail lives behind this tab. */
export const EVIDENCE_INSTRUMENT_ID = "evidence";

/** Max pinned favorites (M028.A). Non-sensitive UI pref only. */
export const MAX_DOCK_PINS = 3;

const CORE_INSTRUMENTS: InstrumentDescriptor[] = [
  {
    id: EVIDENCE_INSTRUMENT_ID,
    title: "Evidence",
    glyph: "◈",
    status: "ready",
    blurb: "Case records with source and collection time.",
  },
  {
    id: "process-watch",
    title: "Process Watch",
    glyph: "◔",
    status: "coming-soon",
    blurb: "Live process observation.",
    unavailableNote:
      "Process Watch is not implemented in this build. No processes are listed, measured, or affected here.",
  },
  {
    id: "event-decoder",
    title: "Event Decoder",
    glyph: "▤",
    status: "coming-soon",
    blurb: "Windows event interpretation.",
    unavailableNote:
      "Event Decoder is not implemented in this build. No events are read or decoded here.",
  },
  {
    id: "command-deck",
    title: "Command Deck",
    glyph: "⌁",
    status: "coming-soon",
    blurb: "Consented diagnostic actions.",
    unavailableNote:
      "Command Deck is not implemented in this build. No commands run from here.",
  },
  {
    id: "field-notes",
    title: "Field Notes",
    glyph: "✎",
    status: "coming-soon",
    blurb: "Technician scratch notes.",
    unavailableNote:
      "Field Notes is not implemented in this build. Use the investigation workspace notes until it ships.",
  },
];

const extraInstruments: InstrumentDescriptor[] = [];

/** Register an additional instrument (M028.B/C panels). Idempotent per id. */
export function registerInstrument(descriptor: InstrumentDescriptor): void {
  const known = [...CORE_INSTRUMENTS, ...extraInstruments].some(
    (entry) => entry.id === descriptor.id,
  );
  if (!known) extraInstruments.push(descriptor);
}

/** Snapshot of every known instrument, core first, in tab order. */
export function listInstruments(): InstrumentDescriptor[] {
  return [...CORE_INSTRUMENTS, ...extraInstruments];
}

export function isKnownInstrument(id: string): boolean {
  return listInstruments().some((entry) => entry.id === id);
}

export function getInstrument(id: string): InstrumentDescriptor | null {
  return listInstruments().find((entry) => entry.id === id) ?? null;
}
