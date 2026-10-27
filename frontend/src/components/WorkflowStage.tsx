import type { InvestigationResponse } from "../types";

export type WorkflowStage = 1 | 2 | 3;

export function stageOf(inv: InvestigationResponse | null): WorkflowStage {
  if (!inv) return 1;
  if (inv.proposals.length > 0 || inv.executions.length > 0 || inv.plans.length > 0) return 3;
  return 2;
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
  const plan = inv.plans.length > 0 ? inv.plans[inv.plans.length - 1] : null;
  if (plan) {
    if (plan.status === "VERIFIED_RESOLVED") {
      return { label: "RESOLVED — verified by measurement", tone: "good" };
    }
    if (plan.status === "NOT_RESOLVED") {
      return { label: "UNRESOLVED — verified outcome: NOT_RESOLVED", tone: "bad" };
    }
    if (plan.status === "INCONCLUSIVE") {
      return { label: "INCONCLUSIVE — measurements insufficient, see plan", tone: "warn" };
    }
    return { label: `RESOLUTION ${plan.status} — see Resolution workspace`, tone: "warn" };
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
