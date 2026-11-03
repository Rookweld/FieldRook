import { useCallback, useRef, useState } from "react";
import { getInvestigation, reverifyEvidence } from "../../api";
import type { InvestigationResponse } from "../../types";
import { formatApiError } from "./formatError";

export interface NetworkLabBinding {
  investigation: InvestigationResponse | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

/**
 * M028.C Network Lab actions. Re-checks go through the EXISTING safe API
 * path (POST .../reverify): the backend re-runs the exact registered
 * read-only tool call with its own timeout, result cap, tool budget, audit
 * trail, and target isolation. One re-check at a time; cancellation drops
 * the local wait (AbortController) and says plainly that the server-side
 * reading may still land — Refresh then shows it.
 */
export function useNetworkLab(binding: NetworkLabBinding): {
  busyId: string | null;
  error: string | null;
  notice: string | null;
  recheck: (evidenceId: string) => Promise<void>;
  cancel: () => void;
  refresh: () => Promise<void>;
  clearStatus: () => void;
} {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  const fail = useCallback((what: string, e: unknown): void => {
    // Abort detection via the signal: api.ts wraps the rejection, so the
    // DOMException name does not survive — the flag is authoritative.
    if (abortRef.current?.signal.aborted) {
      const message =
        "Re-check cancelled locally. If the server already recorded a reading, Refresh will show it.";
      setNotice(message);
      return;
    }
    const message = formatApiError(e, what);
    setError(message);
    bindingRef.current.onError?.(message);
  }, []);

  const recheck = useCallback(
    async (evidenceId: string): Promise<void> => {
      const { investigation, onUpdate, disabled } = bindingRef.current;
      if (disabled || busyRef.current) return;
      if (!investigation) {
        setError("No investigation is open.");
        return;
      }
      busyRef.current = true;
      setBusyId(evidenceId);
      setError(null);
      setNotice(null);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const next = await reverifyEvidence(investigation.investigation_id, evidenceId, {
          signal: controller.signal,
        });
        const fresh = next.evidence.find((item) => item.refresh_of === evidenceId) ?? null;
        const verdict =
          next.refreshes.find((record) => record.old_evidence_id === evidenceId)?.verdict ??
          null;
        onUpdate(next);
        setNotice(
          fresh
            ? `Fresh reading recorded as ${fresh.id}${verdict ? ` (${verdict})` : ""}.`
            : "Re-check finished; case updated.",
        );
      } catch (e) {
        fail("Re-check", e);
      } finally {
        busyRef.current = false;
        abortRef.current = null;
        setBusyId(null);
      }
    },
    [fail],
  );

  const cancel = useCallback((): void => {
    abortRef.current?.abort();
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    const { investigation, onUpdate, disabled } = bindingRef.current;
    if (disabled || busyRef.current) return;
    if (!investigation) {
      setError("No investigation is open.");
      return;
    }
    busyRef.current = true;
    setBusyId("__refresh");
    setError(null);
    try {
      onUpdate(await getInvestigation(investigation.investigation_id));
      setNotice("Case refreshed from the server.");
    } catch (e) {
      fail("Refresh case", e);
    } finally {
      busyRef.current = false;
      setBusyId(null);
    }
  }, [fail]);

  const clearStatus = useCallback((): void => {
    setError(null);
    setNotice(null);
  }, []);

  return { busyId, error, notice, recheck, cancel, refresh, clearStatus };
}
