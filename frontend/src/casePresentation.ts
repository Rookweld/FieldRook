import type { CaseDisposition, InvestigationResponse } from "./types";

/** One vocabulary across history, workbench, filing and reports.
 * Filing is administrative; even "resolved" does not imply measured proof. */
export const CASE_DISPOSITION_LABELS: Record<CaseDisposition, string> = {
  open: "Open",
  resolved: "Resolved · technician-reported",
  needs_followup: "Waiting for follow-up",
  handed_off: "Handed off",
};

const SHORT_LABELS: Record<CaseDisposition, string> = {
  open: "Open",
  resolved: "Resolved (reported)",
  needs_followup: "Follow-up",
  handed_off: "Handed off",
};

export function caseDispositionLabel(
  status?: CaseDisposition | null,
  short = false,
): string {
  const normalized = status ?? "open";
  return (short ? SHORT_LABELS : CASE_DISPOSITION_LABELS)[normalized];
}

/** A recorded technical verification is separate from the technician's filing.
 * This says evidence of a verification is on record; not that a fix still holds. */
export function hasRecordedVerifiedResolution(inv: InvestigationResponse): boolean {
  return inv.plans.some((plan) => plan.status === "VERIFIED_RESOLVED") ||
    inv.proposals.some((proposal) => proposal.status === "VERIFIED_RESOLVED") ||
    inv.executions.some((execution) => execution.outcome === "VERIFIED_RESOLVED");
}
