import { useEffect, useState } from "react";
import {
  ApiError,
  captureBaseline,
  createPlan,
  getPlanTemplate,
  linkPlanExecution,
  listTools,
  recordManualIntervention,
  verifyPlan,
  type CriterionDraft,
  type PlanCreateArgs,
} from "../api";
import type {
  InvestigationResponse,
  PlanStatus,
  ResolutionPlan,
  ToolInfo,
} from "../types";
import { EmptyState } from "./EmptyState";
import { EvidenceChip } from "./EvidenceChip";

const STATUS_CLASS: Record<PlanStatus, string> = {
  DRAFT: "badge",
  BASELINED: "badge badge-sim",
  INTERVENED: "badge badge-sim",
  VERIFIED_RESOLVED: "badge badge-verified",
  NOT_RESOLVED: "badge badge-fail",
  INCONCLUSIVE: "badge",
};

const RESULT_CLASS: Record<string, string> = {
  pass: "verdict verdict-pass",
  fail: "verdict verdict-unavailable",
  inconclusive: "verdict verdict-changed",
};

const OPS = ["eq", "ne", "contains", "gt", "gte", "lt", "lte", "exists"];

function fmtValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function parseJsonLoose(text: string): unknown {
  const trimmed = text.trim();
  if (trimmed === "") return {};
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

interface DraftRow extends CriterionDraft {
  key: number;
  argsText: string;
  expectedText: string;
}

function emptyRow(key: number, toolName: string): DraftRow {
  return {
    key,
    description: "",
    tool_name: toolName,
    tool_args: {},
    argsText: "{}",
    path: "",
    op: "eq",
    expected: "",
    expectedText: "",
  };
}

function PlanForm({
  investigation,
  tools,
  busy,
  onCreate,
}: {
  investigation: InvestigationResponse;
  tools: ToolInfo[];
  busy: boolean;
  onCreate: (args: PlanCreateArgs) => void;
}) {
  const [intended, setIntended] = useState("");
  const [checked, setChecked] = useState<string[]>([]);
  const [kind, setKind] = useState<"manual" | "action">("manual");
  const [guidance, setGuidance] = useState("");
  const [risks, setRisks] = useState("");
  const [rows, setRows] = useState<DraftRow[]>([
    emptyRow(0, tools[0]?.name ?? "get_demo_worker_health"),
  ]);
  const [formError, setFormError] = useState<string | null>(null);

  const usable = investigation.evidence.filter((e) => !e.error);

  const useTemplate = async () => {
    setFormError(null);
    try {
      const template = await getPlanTemplate("recover_demo_worker");
      setIntended(template.intended_state);
      setGuidance(template.guidance);
      setRisks(template.risks);
      setKind("action");
      setRows(
        template.criteria.map((c, i) => ({
          key: i,
          description: c.description,
          tool_name: c.tool_name,
          tool_args: c.tool_args,
          argsText: JSON.stringify(c.tool_args),
          path: c.path,
          op: c.op,
          expected: c.expected,
          expectedText:
            typeof c.expected === "string" ? c.expected : JSON.stringify(c.expected),
        })),
      );
      const worker = usable.filter((e) => e.tool_name === "get_demo_worker_health");
      setChecked(worker.map((e) => e.id));
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  const toggle = (id: string) =>
    setChecked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const submit = () => {
    setFormError(null);
    const criteria: CriterionDraft[] = [];
    for (const row of rows) {
      let args: unknown;
      try {
        args = row.argsText.trim() === "" ? {} : JSON.parse(row.argsText);
      } catch {
        setFormError(`Criterion arguments must be JSON: ${row.argsText}`);
        return;
      }
      if (typeof args !== "object" || args === null || Array.isArray(args)) {
        setFormError("Criterion arguments must be a JSON object.");
        return;
      }
      criteria.push({
        description: row.description.trim(),
        tool_name: row.tool_name,
        tool_args: args as Record<string, unknown>,
        path: row.path.trim(),
        op: row.op,
        expected: parseJsonLoose(row.expectedText),
      });
    }
    onCreate({
      investigationId: investigation.investigation_id,
      evidence_ids: checked,
      intended_state: intended.trim(),
      criteria,
      guidance: guidance.trim(),
      risks: risks.trim(),
      remediation_kind: kind,
      ...(kind === "action"
        ? { action_id: "recover_demo_worker", target: "demo-worker" }
        : {}),
    });
  };

  return (
    <div className="plan-form">
      <div className="controls">
        <button type="button" className="button button-ghost" disabled={busy} onClick={() => void useTemplate()}>
          Use demo-worker recovery template
        </button>
        <span className="muted">prefills measurable criteria — or draft manually below</span>
      </div>
      {formError && (
        <p className="warn" role="alert">
          {formError}
        </p>
      )}
      <label className="field">
        <span>Intended healthy state (must be measurable)</span>
        <textarea
          className="problem"
          rows={2}
          maxLength={2000}
          placeholder="Demo worker reports healthy with a fresh heartbeat."
          value={intended}
          onChange={(e) => setIntended(e.target.value)}
          disabled={busy}
        />
      </label>
      <div className="field">
        <span>Supporting evidence</span>
        <div className="evidence-pick">
          {usable.map((e) => (
            <label key={e.id} className="check">
              <input
                type="checkbox"
                checked={checked.includes(e.id)}
                onChange={() => toggle(e.id)}
                disabled={busy}
              />
              <span>
                {e.id} · {e.category}
              </span>
            </label>
          ))}
          {usable.length === 0 && <span className="muted">No usable evidence.</span>}
        </div>
      </div>
      <div className="field">
        <span>Remediation</span>
        <div className="controls">
          <label className="check">
            <input
              type="radio"
              name="remediation"
              checked={kind === "manual"}
              onChange={() => setKind("manual")}
              disabled={busy}
            />
            <span>Manual (technician-performed)</span>
          </label>
          <label className="check">
            <input
              type="radio"
              name="remediation"
              checked={kind === "action"}
              onChange={() => setKind("action")}
              disabled={busy}
            />
            <span>Registered action (recover_demo_worker → demo-worker)</span>
          </label>
        </div>
      </div>
      {rows.map((row, i) => (
        <fieldset key={row.key} className="criterion-row">
          <legend>Criterion {i + 1}</legend>
          <label className="field">
            <span>Description</span>
            <input
              type="text"
              value={row.description}
              onChange={(e) =>
                setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, description: e.target.value } : r)))
              }
              disabled={busy}
              placeholder="Worker status reads healthy."
            />
          </label>
          <div className="criterion-grid">
            <label className="field">
              <span>Tool</span>
              <select
                value={row.tool_name}
                onChange={(e) =>
                  setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, tool_name: e.target.value } : r)))
                }
                disabled={busy}
              >
                {tools.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Args (JSON)</span>
              <input
                type="text"
                className="mono"
                value={row.argsText}
                onChange={(e) =>
                  setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, argsText: e.target.value } : r)))
                }
                disabled={busy}
              />
            </label>
            <label className="field">
              <span>Path</span>
              <input
                type="text"
                className="mono"
                value={row.path}
                onChange={(e) =>
                  setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, path: e.target.value } : r)))
                }
                disabled={busy}
                placeholder="status"
              />
            </label>
            <label className="field">
              <span>Op</span>
              <select
                value={row.op}
                onChange={(e) =>
                  setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, op: e.target.value } : r)))
                }
                disabled={busy}
              >
                {OPS.map((op) => (
                  <option key={op} value={op}>
                    {op}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Expected</span>
              <input
                type="text"
                className="mono"
                value={row.expectedText}
                onChange={(e) =>
                  setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, expectedText: e.target.value } : r)))
                }
                disabled={busy}
                placeholder="healthy"
              />
            </label>
          </div>
          {rows.length > 1 && (
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => setRows((prev) => prev.filter((r) => r.key !== row.key))}
            >
              Remove criterion
            </button>
          )}
        </fieldset>
      ))}
      <div className="controls">
        <button
          type="button"
          className="button button-ghost"
          disabled={busy || rows.length >= 8}
          onClick={() =>
            setRows((prev) => [...prev, emptyRow(Date.now(), tools[0]?.name ?? "get_demo_worker_health")])
          }
        >
          Add criterion
        </button>
      </div>
      <label className="field">
        <span>Technician guidance</span>
        <textarea
          className="problem"
          rows={2}
          maxLength={2000}
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          disabled={busy}
        />
      </label>
      <label className="field">
        <span>Risks</span>
        <textarea
          className="problem"
          rows={2}
          maxLength={2000}
          value={risks}
          onChange={(e) => setRisks(e.target.value)}
          disabled={busy}
        />
      </label>
      <div className="controls">
        <button
          type="button"
          className="button"
          disabled={busy || checked.length === 0 || intended.trim().length < 10}
          onClick={submit}
        >
          Create resolution plan
        </button>
      </div>
    </div>
  );
}

function PlanCard({
  investigation,
  plan,
  busy,
  onUpdate,
  onEvidenceClick,
}: {
  investigation: InvestigationResponse;
  plan: ResolutionPlan;
  busy: boolean;
  onUpdate: (next: InvestigationResponse) => void;
  onEvidenceClick?: (id: string) => void;
}) {
  const [manualText, setManualText] = useState("");
  const [execId, setExecId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const latest = plan.verifications.length > 0 ? plan.verifications[plan.verifications.length - 1] : null;

  const run = async (key: string, fn: () => Promise<InvestigationResponse>) => {
    if (busy || active) return;
    setActive(key);
    setError(null);
    try {
      onUpdate(await fn());
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Resolution failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setActive(null);
    }
  };

  const resultFor = (criterionId: string) =>
    latest?.results.find((r) => r.criterion_id === criterionId) ?? null;

  const nextStep =
    investigation.suggested_rechecks[0]?.reason ??
    investigation.assessment?.next_steps[0]?.step ??
    investigation.assessment?.next_actions[0] ??
    null;

  // Plan exists from DRAFT on; each lifecycle step completes the next stage.
  const doneCount =
    plan.status === "DRAFT" ? 1 : plan.status === "BASELINED" ? 2 : plan.status === "INTERVENED" ? 3 : 5;
  const stages = ["Plan", "Baseline", "Intervene", "Verify", "Verdict"].map((label, i) => ({
    label,
    state: i < doneCount ? "done" : i === doneCount ? "current" : "todo",
  }));

  return (
    <article className="action-card">
      <div className="card-head">
        <h3 className="action-title">
          Plan <span className="muted">{plan.plan_id}</span>
        </h3>
        <span className={STATUS_CLASS[plan.status]}>{plan.status}</span>
      </div>
      <ol className="stages" aria-label="Resolution progress">
        {stages.map((s) => (
          <li key={s.label} className={`stage stage-${s.state}`} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="stage-dot" aria-hidden="true" />
            {s.label}
          </li>
        ))}
      </ol>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      <p>
        <strong>Intended state:</strong> {plan.intended_state}
      </p>
      <p className="muted">
        Remediation:{" "}
        {plan.remediation_kind === "action"
          ? `registered action ${plan.action_id} → ${plan.target}`
          : "manual (technician-performed)"}{" "}
        · Supporting:{" "}
        {plan.evidence_ids.map((eid) => (
          <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
        ))}
      </p>
      {plan.guidance && (
        <p>
          <span className="runbook-label">Guidance:</span> {plan.guidance}
        </p>
      )}
      {plan.risks && (
        <p>
          <span className="runbook-label">Risks:</span> {plan.risks}
        </p>
      )}

      <ol className="criterion-cards">
        {plan.criteria.map((c) => {
          const result = resultFor(c.criterion_id);
          const before = plan.baseline_values[c.criterion_id];
          const hasBefore = before !== undefined;
          const changed =
            result !== null && hasBefore && fmtValue(before) !== fmtValue(result.observed);
          return (
            <li key={c.criterion_id} className="criterion-card">
              <div className="criterion-head">
                <strong>{c.description}</strong>
                {result ? (
                  <span className={RESULT_CLASS[result.outcome]} title={result.detail}>
                    {result.outcome.toUpperCase()}
                  </span>
                ) : (
                  <span className="verdict verdict-unmeasured">UNMEASURED</span>
                )}
              </div>
              <p className="mono muted criterion-check">
                {c.tool_name} · {c.path} {c.op} {fmtValue(c.expected)}
              </p>
              <div className="criterion-compare">
                <div className="compare-col">
                  <span className="compare-label">Before</span>
                  {hasBefore ? (
                    <>
                      <span className="mono">{fmtValue(before)}</span>{" "}
                      {result?.before_evidence_id && (
                        <EvidenceChip id={result.before_evidence_id} onSelect={onEvidenceClick} />
                      )}
                    </>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </div>
                <span className="compare-arrow" aria-hidden="true">
                  →
                </span>
                <div className={`compare-col${changed ? " compare-changed" : ""}`}>
                  <span className="compare-label">After</span>
                  {result ? (
                    <>
                      <span className="mono">{fmtValue(result.observed)}</span>{" "}
                      {result.after_evidence_id && (
                        <EvidenceChip id={result.after_evidence_id} onSelect={onEvidenceClick} />
                      )}
                    </>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {plan.baseline_captured_at && (
        <p className="muted">
          Baseline captured {new Date(plan.baseline_captured_at).toLocaleString()} (
          {plan.baseline_evidence_ids.map((eid) => (
            <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
          ))}
          )
        </p>
      )}

      {plan.interventions.length > 0 && (
        <ul className="unverified">
          {plan.interventions.map((iv, i) => (
            <li key={i}>
              <span className="tag tag-inf">{iv.kind === "manual" ? "MANUAL CLAIM" : "AUTHORIZED ACTION"}</span>{" "}
              <span>{iv.description}</span>{" "}
              <span className="muted">{new Date(iv.recorded_at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      )}

      {latest && (
        <div
          className={`resolution resolution-${latest.outcome === "VERIFIED_RESOLVED" ? "good resolution-confirm" : latest.outcome === "NOT_RESOLVED" ? "bad" : "warn"}`}
        >
          {latest.outcome} — {latest.results.filter((r) => r.outcome === "pass").length}/
          {latest.results.length} criteria pass ·{" "}
          {new Date(latest.verified_at).toLocaleString()}
        </div>
      )}
      {latest?.uncertainties.map((u, i) => (
        <p key={i} className="warn">
          {u}
        </p>
      ))}
      {(plan.status === "NOT_RESOLVED" || plan.status === "INCONCLUSIVE") && nextStep && (
        <p className="muted">
          <span className="runbook-label">Recommended next step:</span> {nextStep}
        </p>
      )}

      <div className="controls">
        {plan.status === "DRAFT" && (
          <button
            type="button"
            className="button"
            disabled={busy || active !== null}
            onClick={() => void run("baseline", () => captureBaseline(plan.plan_id))}
          >
            {active === "baseline" ? "Capturing…" : "Capture pre-fix baseline"}
          </button>
        )}
        {(plan.status === "BASELINED" || plan.status === "INTERVENED") && (
          <>
            <input
              type="text"
              className="mono manual-input"
              placeholder="What did you do by hand? (claim only — proof needs Confirm Fix)"
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              disabled={busy || active !== null}
              maxLength={1000}
            />
            <button
              type="button"
              className="button button-ghost"
              disabled={busy || active !== null || !manualText.trim()}
              onClick={() => {
                void run("manual", () => recordManualIntervention(plan.plan_id, manualText.trim())).then(
                  () => setManualText(""),
                );
              }}
            >
              {active === "manual" ? "Recording…" : "Record manual fix"}
            </button>
            {investigation.executions.length > 0 && (
              <>
                <select
                  value={execId}
                  onChange={(e) => setExecId(e.target.value)}
                  disabled={busy || active !== null}
                >
                  <option value="">Link an execution…</option>
                  {investigation.executions.map((x) => (
                    <option key={x.execution_id} value={x.execution_id}>
                      {x.execution_id} · {x.outcome}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="button button-ghost"
                  disabled={busy || active !== null || !execId}
                  onClick={() => void run("link", () => linkPlanExecution(plan.plan_id, execId))}
                >
                  {active === "link" ? "Linking…" : "Link execution"}
                </button>
              </>
            )}
          </>
        )}
        {plan.status !== "DRAFT" && plan.status !== "BASELINED" && (
          <button
            type="button"
            className="button"
            disabled={busy || active !== null}
            onClick={() => void run("verify", () => verifyPlan(plan.plan_id))}
          >
            {active === "verify" ? "Verifying…" : "Confirm Fix"}
          </button>
        )}
      </div>
      {plan.status === "BASELINED" && (
        <p className="muted">
          Baseline captured. Perform the fix (Action Center above, or by hand), record it
          here, then Confirm Fix re-measures.
        </p>
      )}
    </article>
  );
}

export function ResolutionWorkspace({
  investigation,
  onUpdate,
  onEvidenceClick,
}: {
  investigation: InvestigationResponse;
  onUpdate: (next: InvestigationResponse) => void;
  onEvidenceClick?: (id: string) => void;
}) {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listTools().then(
      (t) => {
        if (!cancelled) setTools(t);
      },
      () => {
        /* tool list is needed for custom criteria; template still works */
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const create = async (args: PlanCreateArgs) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      onUpdate(await createPlan(args));
      setShowForm(false);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Plan failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <div className="card-head">
        <h2>Resolution workspace</h2>
        <span className="muted">
          {investigation.plans.length} plan{investigation.plans.length === 1 ? "" : "s"} · proof
          from measurement, not claims
        </span>
      </div>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      {investigation.plans.length === 0 && !showForm && (
        <EmptyState
          icon="◇"
          title="No resolution plan yet"
          body="Draft one from the evidence: measurable criteria, a pre-fix baseline, then Confirm Fix re-measures."
        />
      )}
      {investigation.plans.map((plan) => (
        <PlanCard
          key={plan.plan_id}
          investigation={investigation}
          plan={plan}
          busy={busy}
          onUpdate={onUpdate}
          onEvidenceClick={onEvidenceClick}
        />
      ))}
      {!showForm ? (
        <div className="controls">
          <button
            type="button"
            className={investigation.plans.length === 0 ? "button" : "button button-ghost"}
            disabled={busy}
            onClick={() => setShowForm(true)}
          >
            New resolution plan
          </button>
        </div>
      ) : (
        <>
          <PlanForm investigation={investigation} tools={tools} busy={busy} onCreate={(a) => void create(a)} />
          <div className="controls">
            <button
              type="button"
              className="button button-ghost"
              disabled={busy}
              onClick={() => setShowForm(false)}
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </section>
  );
}
