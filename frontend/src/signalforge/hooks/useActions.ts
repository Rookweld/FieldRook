import { useCallback, useRef, useState } from "react";
import {
  approveProposal,
  executeProposal,
  getInvestigation,
  proposeAction,
  rejectProposal,
} from "../../api";
import type { InvestigationResponse } from "../../types";
import { formatApiError } from "./formatError";

export interface ActionsBinding {
  investigation: InvestigationResponse | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

interface ApprovalTicket {
  token: string;
  expiresAtMs: number;
}

/**
 * Approval/execution split, preserved exactly: propose -> approve (holds
 * a memory-only ticket) -> execute (spends it). Tokens are never
 * rendered and never persisted; only ticket presence is exposed.
 * A failed execute drops the ticket and resyncs from the server, so the
 * UI shows the server's real state (mirrors ActionCenter).
 */
export function useActions(binding: ActionsBinding): {
  busy: string | null;
  error: string | null;
  approvedIds: string[];
  propose: (actionId: string, target: string, reason: string) => Promise<void>;
  approve: (proposalId: string) => Promise<void>;
  reject: (proposalId: string) => Promise<void>;
  execute: (proposalId: string) => Promise<void>;
  clearError: () => void;
} {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approvedIds, setApprovedIds] = useState<string[]>([]);
  const busyRef = useRef<string | null>(null);
  const ticketsRef = useRef<Record<string, ApprovalTicket>>({});
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  const fail = useCallback((what: string, e: unknown) => {
    const message = formatApiError(e, what);
    setError(message);
    bindingRef.current.onError?.(message);
  }, []);

  const propose = useCallback(
    async (actionId: string, target: string, reason: string) => {
      const { investigation, onUpdate, disabled } = bindingRef.current;
      if (disabled || busyRef.current) return;
      if (!investigation) {
        fail("Propose action", new Error("No investigation is open."));
        return;
      }
      busyRef.current = "propose";
      setBusy("propose");
      setError(null);
      try {
        onUpdate(
          await proposeAction({
            investigationId: investigation.investigation_id,
            actionId,
            target,
            reason,
          }),
        );
      } catch (e) {
        fail("Propose action", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail],
  );

  const approve = useCallback(
    async (proposalId: string) => {
      const { onUpdate, disabled } = bindingRef.current;
      if (disabled || busyRef.current) return;
      busyRef.current = `approve-${proposalId}`;
      setBusy(busyRef.current);
      setError(null);
      try {
        const approval = await approveProposal(proposalId);
        ticketsRef.current[proposalId] = {
          token: approval.approval_token,
          expiresAtMs: Date.now() + approval.expires_in_s * 1000,
        };
        setApprovedIds((prev) => (prev.includes(proposalId) ? prev : [...prev, proposalId]));
        onUpdate(approval.investigation);
      } catch (e) {
        fail("Approve proposal", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail],
  );

  const reject = useCallback(
    async (proposalId: string) => {
      const { onUpdate, disabled } = bindingRef.current;
      if (disabled || busyRef.current) return;
      busyRef.current = `reject-${proposalId}`;
      setBusy(busyRef.current);
      setError(null);
      try {
        onUpdate(await rejectProposal(proposalId));
      } catch (e) {
        fail("Reject proposal", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail],
  );

  const execute = useCallback(
    async (proposalId: string) => {
      const { investigation, onUpdate, disabled } = bindingRef.current;
      if (disabled || busyRef.current) return;
      const ticket = ticketsRef.current[proposalId];
      if (!ticket) {
        fail("Execute proposal", new Error("Approve this proposal first — nothing runs automatically."));
        return;
      }
      busyRef.current = `execute-${proposalId}`;
      setBusy(busyRef.current);
      setError(null);
      try {
        const result = await executeProposal(proposalId, ticket.token);
        delete ticketsRef.current[proposalId];
        setApprovedIds((prev) => prev.filter((id) => id !== proposalId));
        onUpdate(result.investigation);
      } catch (e) {
        delete ticketsRef.current[proposalId];
        setApprovedIds((prev) => prev.filter((id) => id !== proposalId));
        if (investigation) {
          try {
            onUpdate(await getInvestigation(investigation.investigation_id));
          } catch {
            /* resync is best-effort; the original error below is what matters */
          }
        }
        fail("Execute proposal", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { busy, error, approvedIds, propose, approve, reject, execute, clearError };
}
