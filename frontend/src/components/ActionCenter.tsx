import { useState } from "react";
import {
  ApiError,
  approveProposal,
  executeProposal,
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
  REJECTED: "badge",
  EXECUTING: "badge badge-sim",
  EXECUTED_UNVERIFIED: "badge badge-sim",
  VERIFIED_RESOLVED: "badge badge-live",
  VERIFIED_UNRESOLVED: "badge",
  EXECUTION_FAILED: "badge badge-fail",
  VERIFICATION_FAILED: "badge badge-fail",
};

function BeforeAfter({ execution }: { execution: ActionExecution }) {
  const before = execution.before_state["status"];
  const after = execution.after_state["status"];
  return (
    <div className="before-after">
      <div>
        <span className="muted">BEFORE</span>
        <pre className="pre small">{JSON.stringify(execution.before_state, null, 2)}</pre>
      </div>
      <div>
        <span className="muted">AFTER</span>
        <pre className="pre small">{JSON.stringify(execution.after_state, null, 2)}</pre>
      </div>
      <p className="muted">
        {typeof before === "string" && typeof after === "string"
          ? `${before} → ${after}`
          : `outcome: ${execution.outcome}`}
      </p>
    </div>
  );
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

  const approveThenExecute = (proposal: ActionProposal) =>
    run(`exec-${proposal.proposal_id}`, async () => {
      const approval = await approveProposal(proposal.proposal_id);
      const result = await executeProposal(proposal.proposal_id, approval.approval_token);
      return result.investigation;
    });

  return (
    <section className="card">
      <div className="card-head">
        <h2>
          <span className="eyebrow">Stage 3 — Resolve</span>Action Center
        </h2>
        <span className="muted">human approval required — nothing runs automatically</span>
      </div>
      {error && <p className="warn">{error}</p>}

      {investigation.proposals.length === 0 && investigation.executions.length === 0 && (
        <p className="muted">
          No corrective action proposed for this investigation. Only the registered
          demo-worker recovery is available; diagnostics stay read-only.
        </p>
      )}

      {investigation.proposals.map((proposal) => (
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
                onClick={() => void approveThenExecute(proposal)}
              >
                {busy === `exec-${proposal.proposal_id}`
                  ? "Approving & executing…"
                  : "Approve & execute"}
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
        </article>
      ))}

      {investigation.executions.map((execution) => (
        <article key={execution.execution_id} className="action-card">
          <div className="card-head">
            <h3 className="action-title">
              Execution <span className="muted">{execution.execution_id}</span>
            </h3>
            <span className={STATUS_CLASS[execution.outcome]}>{execution.outcome}</span>
          </div>
          <p className="muted">
            {execution.action_id} → {execution.target} · started{" "}
            {new Date(execution.started_at).toLocaleString()}
            {execution.finished_at &&
              ` · finished ${new Date(execution.finished_at).toLocaleString()}`}
          </p>
          {execution.error && <p className="warn">{execution.error}</p>}
          <BeforeAfter execution={execution} />
        </article>
      ))}

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
