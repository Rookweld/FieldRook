import { useCallback, useRef, useState } from "react";
import {
  addInvestigationNote,
  cancelRound,
  followUpInvestigation,
  getInvestigation,
  reverifyEvidence,
  sendTurn,
  startInvestigation,
  type StartInvestigationArgs,
  type TurnArgs,
} from "../../api";
import type { InvestigationResponse } from "../../types";
import { formatApiError } from "./formatError";

export interface UseInvestigationOptions {
  initial?: InvestigationResponse | null;
  onError?: (message: string) => void;
}

/**
 * Owns the open investigation (the full-replace pattern: every mutation
 * returns the whole InvestigationResponse and replaces state). Covers
 * start/open/refresh, turns, follow-ups, notes, cancellation, and
 * evidence re-verification. `busy` names the in-flight op (or null);
 * only one mutation runs at a time.
 */
export function useInvestigation(options: UseInvestigationOptions = {}): {
  investigation: InvestigationResponse | null;
  busy: string | null;
  error: string | null;
  start: (args: StartInvestigationArgs) => Promise<InvestigationResponse | null>;
  open: (id: string) => Promise<InvestigationResponse | null>;
  refresh: () => Promise<InvestigationResponse | null>;
  send: (args: TurnArgs) => Promise<InvestigationResponse | null>;
  followUp: (message: string) => Promise<InvestigationResponse | null>;
  addNote: (text: string) => Promise<InvestigationResponse | null>;
  cancel: () => Promise<InvestigationResponse | null>;
  reverify: (evidenceId: string) => Promise<InvestigationResponse | null>;
  update: (next: InvestigationResponse) => void;
  clearError: () => void;
} {
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(
    options.initial ?? null,
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);
  const onErrorRef = useRef(options.onError);
  onErrorRef.current = options.onError;
  const idRef = useRef<string | null>(options.initial?.investigation_id ?? null);
  idRef.current = investigation?.investigation_id ?? idRef.current;

  const fail = useCallback((what: string, e: unknown): null => {
    const message = formatApiError(e, what);
    setError(message);
    onErrorRef.current?.(message);
    return null;
  }, []);

  const run = useCallback(
    async (key: string, what: string, fn: () => Promise<InvestigationResponse>) => {
      if (busyRef.current) return null;
      busyRef.current = key;
      setBusy(key);
      setError(null);
      try {
        const next = await fn();
        idRef.current = next.investigation_id;
        setInvestigation(next);
        return next;
      } catch (e) {
        return fail(what, e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail],
  );

  const requireId = useCallback((): string | null => {
    const id = idRef.current;
    if (!id) {
      const message = "No investigation is open.";
      setError(message);
      onErrorRef.current?.(message);
    }
    return id;
  }, []);

  const start = useCallback(
    (args: StartInvestigationArgs) => run("start", "Investigation start", () => startInvestigation(args)),
    [run],
  );

  const open = useCallback(
    (id: string) => run("open", "Open investigation", () => getInvestigation(id)),
    [run],
  );

  const refresh = useCallback(async () => {
    const id = requireId();
    if (!id) return null;
    return run("refresh", "Refresh investigation", () => getInvestigation(id));
  }, [requireId, run]);

  const send = useCallback(
    async (args: TurnArgs) => {
      const id = requireId();
      if (!id) return null;
      return run("turn", "Send turn", () => sendTurn(id, args));
    },
    [requireId, run],
  );

  const followUp = useCallback(
    async (message: string) => {
      const id = requireId();
      if (!id) return null;
      return run("followup", "Follow-up", () => followUpInvestigation(id, message));
    },
    [requireId, run],
  );

  const addNote = useCallback(
    async (text: string) => {
      const id = requireId();
      if (!id) return null;
      return run("note", "Save note", () => addInvestigationNote(id, text));
    },
    [requireId, run],
  );

  const cancel = useCallback(async () => {
    const id = requireId();
    if (!id) return null;
    return run("cancel", "Cancel round", () => cancelRound(id));
  }, [requireId, run]);

  const reverify = useCallback(
    async (evidenceId: string) => {
      const id = requireId();
      if (!id) return null;
      return run("reverify", "Re-verify evidence", () => reverifyEvidence(id, evidenceId));
    },
    [requireId, run],
  );

  const update = useCallback((next: InvestigationResponse) => {
    idRef.current = next.investigation_id;
    setInvestigation(next);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    investigation,
    busy,
    error,
    start,
    open,
    refresh,
    send,
    followUp,
    addNote,
    cancel,
    reverify,
    update,
    clearError,
  };
}
