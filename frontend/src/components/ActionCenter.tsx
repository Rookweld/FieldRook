import { useState } from "react";
import {
  ApiError,
  approveProposal,
  executeProposal,
  getInvestigation,
  proposeAction,
  rejectProposal,
} from "../api";
import type {
  ActionExecution,
  ActionProposal,
  InvestigationResponse,
  ProposalStatus,
} from "../types";

const STATUS_CLASS: Record<ProposalStatus, string> = {
  PROPOSED: "badge",
  AWAITING_APPROVAL: "badge badge-sim",
  APPROVED: "badge badge-live",
  REJECTED: "badge",
  EXECUTING: "badge badge-sim",
  EXECUTED_UNVERIFIED: "badge badge-sim",
  VERIFIED_RESOLVED: "badge badge-verified",
  VERIFIED_UNRESOLVED: "badge",
  EXECUTION_FAILED: "badge badge-fail",
  VERIFICATION_FAILED: "badge badge-fail",
};

function stateWord(execution: ActionExecution, which: "before" | "after"): string {
  const state = which === "before" ? execution.before_state : execution.after_state;
  const status = state["status"];
  return typeof status === "string" ? status.toUpperCase() : "?";
}

function ResultStrip({
  execution,
  actionId,
}: {
  execution: ActionExecution;
  actionId: string;
}) {
  return (
    <div className="result-strip" role="status" aria-label="Verified result">
      <span className="result-cell">
        <span className="eyebrow">Before</span>
        <strong>{stateWord(execution, "before")}</strong>
      </span>
      <span className="result-arrow" aria-hidden="true">
        →
      </span>
      <span className="result-cell">
        <span className="eyebrow">Action</span>
        <strong className="mono">{actionId}</strong>
      </span>
      <span className="result-arrow" aria-hidden="true">
        →
      </span>
      <span className="result-cell">
        <span className="eyebrow">After</span>
        <strong>{stateWord(execution, "after")}</strong>
      </span>
      <span className="result-arrow" aria-hidden="true">
        →
      </span>
      <span className="result-cell">
        <span className="eyebrow">Verified outcome</span>
        <span className={STATUS_CLASS[execution.outcome]}>{execution.outcome}</span>
      </span>
    </div>
  );
}

function BeforeAfter({ execution }: { execution: ActionExecution }) {
  const before = execution.before_state["status"];
  const after = execution.after_state["status"];
  return (
    <div className="before-after">
      <p>
        <span className="muted">BEFORE</span>{" "}
        {typeof before === "string" ? before : "?"} <span aria-hidden="true">→</span>{" "}
        <span className="muted">AFTER</span> {typeof after === "string" ? after : "?"}{" "}
        <span className="muted">· outcome: {execution.outcome}</span>
      </p>
      <details className="ev-json">
        <summary>Full before/after state</summary>
        <pre className="pre small">{JSON.stringify(execution.before_state, null, 2)}</pre>
        <pre className="pre small">{JSON.stringify(execution.after_state, null, 2)}</pre>
      </details>
    </div>
  );
}

interface ApprovalTicket {
  token: string;
  expiresAtMs: number;
}

export function ActionCenter({
  investigation,
  onUpdate,
}: {
  investigation: InvestigationResponse;
  onUpdate: (next: InvestigationResponse) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [reason, setReason] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  // Approval tokens live in memory only: never persisted, never rendered.
  const [tickets, setTickets] = useState<Record<string, ApprovalTicket>>({});

  const run = async (key: string, fn: () => Promise<InvestigationResponse>) => {
    if (busy) return;
    setBusy(key);
    setError(null);
    try {
      onUpdate(await fn());
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Action failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(null);
    }
  };

  const approve = (proposal: ActionProposal) =>
    run(`appr-${proposal.proposal_id}`, async () => {
      const approval = await approveProposal(proposal.proposal_id);
      setTickets((prev) => ({
        ...prev,
        [proposal.proposal_id]: {
          token: approval.approval_token,
          expiresAtMs: Date.now() + approval.expires_in_s * 1000,
        },
      }));
      return approval.investigation;
    });

  const execute = (proposal: ActionProposal, ticket: ApprovalTicket) =>
    run(`exec-${proposal.proposal_id}`, async () => {
      try {
        const result = await executeProposal(proposal.proposal_id, ticket.token);
        setTickets((prev) => {
          const next = { ...prev };
          delete next[proposal.proposal_id];
          return next;
        });
        return result.investigation;
      } catch (e) {
        // Token spent or lapsed: drop it and resync so the UI shows the
        // server's real state (e.g. back to AWAITING_APPROVAL on expiry).
        setTickets((prev) => {
          const next = { ...prev };
          delete next[proposal.proposal_id];
          return next;
        });
        try {
          onUpdate(await getInvestigation(investigation.investigation_id));
        } catch {
          /* resync is best-effort; the original error below is what matters */
        }
        throw e;
      }
    });

  const lastExecution =
    investigation.executions.length > 0
      ? investigation.executions[investigation.executions.length - 1]
      : null;

  return (
    <section className="card">
      <div className="card-head">
        <h2>Action Center</h2>
        <span className="muted">approve first, execute separately — nothing runs automatically</span>
      </div>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}

      {lastExecution && (
        <ResultStrip
          execution={lastExecution}
          actionId={
            investigation.proposals.find((p) => p.proposal_id === lastExecution.proposal_id)
              ?.action_id ?? lastExecution.action_id ?? "?"
          }
        />
      )}

      {investigation.proposals.length === 0 && investigation.executions.length === 0 && (
        <p className="muted">
          No corrective action proposed for this investigation. Only the registered
          demo-worker recovery is available; diagnostics stay read-only.
        </p>
      )}

      {investigation.proposals.map((proposal) => {
        const ticket = tickets[proposal.proposal_id];
        const ticketLive = ticket !== undefined && ticket.expiresAtMs > Date.now();
        return (
          <article key={proposal.proposal_id} className="action-card">
            <div className="card-head">
              <h3 className="action-title">
                {proposal.action_id} <span className="muted">→ {proposal.target}</span>
              </h3>
              <span className={STATUS_CLASS[proposal.status]}>{proposal.status}</span>
            </div>
            <div className="action-grid">
              <div>
                <span className="muted">AI recommendation</span>
                <p className="quote">{proposal.reason}</p>
              </div>
              <div>
                <span className="muted">Expected result</span>
                <p>{proposal.expected_result}</p>
                <span className="muted">Verification</span>
                <p>{proposal.verification}</p>
                <span className="muted">Risk</span>
                <p>{proposal.risk}</p>
              </div>
            </div>
            {proposal.evidence_ids.length > 0 && (
              <div className="tl-refs">
                {proposal.evidence_ids.map((eid) => (
                  <code key={eid} className="chip">
                    {eid}
                  </code>
                ))}
              </div>
            )}
            {proposal.decision && (
              <p className="muted">
                Technician decision: {proposal.decision}
                {proposal.decided_at && ` · ${new Date(proposal.decided_at).toLocaleString()}`}
              </p>
            )}
            {proposal.status === "AWAITING_APPROVAL" && (
              <div className="controls">
                <button
                  type="button"
                  className="button"
                  disabled={busy !== null}
                  onClick={() => void approve(proposal)}
                >
                  {busy === `appr-${proposal.proposal_id}` ? "Approving…" : "Approve action"}
                </button>
                <button
                  type="button"
                  className="button button-ghost"
                  disabled={busy !== null}
                  onClick={() =>
                    void run(`rej-${proposal.proposal_id}`, () =>
                      rejectProposal(proposal.proposal_id),
                    )
                  }
                >
                  {busy === `rej-${proposal.proposal_id}` ? "Rejecting…" : "Reject action"}
                </button>
              </div>
            )}
            {proposal.status === "APPROVED" && (
              <div>
                {ticketLive ? (
                  <p className="approval-note">
                    Approved — nothing has executed yet. Single-use authorization, lapses
                    within minutes. Executing runs exactly this action on this target.
                  </p>
                ) : (
                  <p className="warn">
                    Approved earlier, but no usable authorization is held here (it may
                    have lapsed or this view was reloaded). Approve again for a fresh
                    single-use token.
                  </p>
                )}
                <div className="controls">
                  {ticketLive && (
                    <button
                      type="button"
                      className="button button-danger"
                      disabled={busy !== null}
                      onClick={() => void execute(proposal, ticket)}
                    >
                      {busy === `exec-${proposal.proposal_id}`
                        ? "Executing…"
                        : "Execute approved action"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="button button-ghost"
                    disabled={busy !== null}
                    onClick={() => void approve(proposal)}
                  >
                    {busy === `appr-${proposal.proposal_id}`
                      ? "Approving…"
                      : ticketLive
                        ? "Re-approve (fresh token)"
                        : "Approve again"}
                  </button>
                </div>
              </div>
            )}
          </article>
        );
      })}

      {investigation.executions.map((execution) => {
        const proposal = investigation.proposals.find(
          (p) => p.proposal_id === execution.proposal_id,
        );
        const actionId = proposal ? proposal.action_id : execution.action_id;
        const target = proposal ? proposal.target : execution.target;
        return (
          <article key={execution.execution_id} className="action-card">
            <div className="card-head">
              <h3 className="action-title">
                Execution <span className="muted">{execution.execution_id}</span>
              </h3>
              <span className={STATUS_CLASS[execution.outcome]}>{execution.outcome}</span>
            </div>
            <p className="muted">
              {actionId} → {target} · started{" "}
            {new Date(execution.started_at).toLocaleString()}
            {execution.finished_at &&
              ` · finished ${new Date(execution.finished_at).toLocaleString()}`}
          </p>
            {execution.error && <p className="warn">{execution.error}</p>}
            <BeforeAfter execution={execution} />
          </article>
        );
      })}

      <details>
        <summary>Request a proposal manually</summary>
        <label className="field">
          <span>Reason (technician request)</span>
          <textarea
            className="problem"
            rows={2}
            maxLength={2000}
            placeholder="The demo worker is unhealthy and needs recovery."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy !== null}
          />
        </label>
        <div className="controls">
          <button
            type="button"
            className="button button-ghost"
            disabled={busy !== null || !reason.trim()}
            onClick={() =>
              void run("propose", () =>
                proposeAction({
                  investigationId: investigation.investigation_id,
                  actionId: "recover_demo_worker",
                  target: "demo-worker",
                  reason: reason.trim(),
                }),
              )
            }
          >
            {busy === "propose" ? "Requesting…" : "Propose demo-worker recovery"}
          </button>
        </div>
      </details>
    </section>
  );
}
