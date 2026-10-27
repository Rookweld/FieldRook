import type { InvestigationResponse } from "../types";

export type WorkflowStage = 1 | 2 | 3;

export function stageOf(inv: InvestigationResponse | null): WorkflowStage {
  if (!inv) return 1;
  if (inv.proposals.length > 0 || inv.executions.length > 0) return 3;
  return 2;
}

const STAGES: Array<{ n: WorkflowStage; name: string; hint: string }> = [
  { n: 1, name: "Investigate", hint: "describe symptoms" },
  { n: 2, name: "Understand", hint: "evidence + hypotheses" },
  { n: 3, name: "Resolve", hint: "approve, verify, export" },
];

export function StageStepper({ stage }: { stage: WorkflowStage }) {
  return (
    <nav className="stages" aria-label="Workflow stage">
      {STAGES.map((s) => (
        <div
          key={s.n}
          className={
            s.n === stage ? "stage stage-active" : s.n < stage ? "stage stage-done" : "stage"
          }
          aria-current={s.n === stage ? "step" : undefined}
        >
          <span className="stage-num">{s.n}</span>
          <span className="stage-name">{s.name}</span>
          <span className="stage-hint">{s.hint}</span>
        </div>
      ))}
    </nav>
  );
}

export interface Resolution {
  label: string;
  tone: "good" | "bad" | "warn" | "mute";
}

export function resolutionOf(inv: InvestigationResponse): Resolution {
  const last = inv.executions.length > 0 ? inv.executions[inv.executions.length - 1] : null;
  if (last) {
    if (last.outcome === "VERIFIED_RESOLVED") {
      return { label: "RESOLVED — independently verified", tone: "good" };
    }
    return { label: `UNRESOLVED — verified outcome: ${last.outcome}`, tone: "bad" };
  }
  if (inv.proposals.some((p) => p.status === "AWAITING_APPROVAL")) {
    return { label: "AWAITING DECISION — approval required, nothing executed", tone: "warn" };
  }
  if (inv.proposals.some((p) => p.status === "APPROVED")) {
    return { label: "APPROVED — authorized, awaiting deliberate execution", tone: "warn" };
  }
  if (inv.proposals.some((p) => p.status === "REJECTED")) {
    return { label: "NO ACTION — rejected by technician, system unchanged", tone: "mute" };
  }
  if (inv.proposals.length > 0) {
    return { label: "ACTION RECORDED — see Action Center", tone: "warn" };
  }
  return { label: "UNRESOLVED — diagnosed, no verified correction", tone: "mute" };
}
