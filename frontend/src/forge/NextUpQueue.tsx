import { nextActionFor } from "../components/OverviewPanel";
import type { ForgeNavigateTarget, NextUpQueueProps } from "./types";
import "./forge.css";

/**
 * Ordered work queue. The head is `nextActionFor(investigation)` — the same
 * single next action the overview shows — so "run next" always matches the
 * existing UI. The tail lists the current plan step, open questions,
 * upcoming steps, and suggested rechecks, each navigating via onAction.
 */
export function NextUpQueue({ investigation, onAction, onView }: NextUpQueueProps) {
  const head = nextActionFor(investigation);
  const openQuestions = investigation.questions.filter((q) => q.status === "open");
  const currentStep =
    investigation.plan?.steps.find((s) => s.step_id === investigation.plan?.current_step_id) ??
    null;
  const upcomingSteps = (investigation.plan?.steps ?? [])
    .filter((s) => s.status === "suggested" && s.step_id !== investigation.plan?.current_step_id)
    .slice(0, 2);
  const budgetLeft = investigation.tool_calls_max - investigation.tool_calls_used;

  const go = (target: ForgeNavigateTarget) => {
    onAction?.("navigate", target);
    onView?.(target.view);
  };

  const queue: { key: string; label: string; detail: string; target: ForgeNavigateTarget }[] = [];
  if (currentStep) {
    queue.push({
      key: `step-${currentStep.step_id}`,
      label: "Work the current step",
      detail: currentStep.instruction,
      target: { label: "Work the next step", view: "guide" },
    });
  }
  for (const q of openQuestions.slice(0, 3)) {
    queue.push({
      key: `q-${q.question_id}`,
      label: "Answer the question",
      detail: q.question,
      target: { label: "Answer clarifying question", view: "guide" },
    });
  }
  for (const s of upcomingSteps) {
    queue.push({
      key: `up-${s.step_id}`,
      label: "Upcoming step",
      detail: s.instruction,
      target: { label: "Work the next step", view: "guide" },
    });
  }
  if (investigation.suggested_rechecks.length > 0 && budgetLeft > 0) {
    queue.push({
      key: "recheck",
      label: "Re-check stale evidence",
      detail: `${investigation.suggested_rechecks.length} suggestion${investigation.suggested_rechecks.length === 1 ? "" : "s"} · ${budgetLeft} tool calls left`,
      target: { label: "Re-check stale evidence", view: "findings" },
    });
  }

  return (
    <section className="card forge-queue" data-testid="forge-next-up" aria-label="Next up">
      <div className="card-head">
        <h2>
          <span className="eyebrow">Next up</span>
        </h2>
      </div>
      <div className="forge-head">
        <span className="result-next-label">Head of queue</span>
        <p className="forge-head-label">{head.label}</p>
        <div className="controls">
          <button
            type="button"
            className="button"
            data-testid="forge-next-run"
            onClick={() => go({ label: head.label, view: head.view, focusId: head.focusId })}
          >
            Run next: {head.label}
          </button>
        </div>
      </div>
      {queue.length > 0 && (
        <ol className="forge-queue-list">
          {queue.map((item) => (
            <li key={item.key}>
              <button
                type="button"
                className="forge-queue-row"
                onClick={() => go(item.target)}
                title={item.detail}
              >
                <span className="forge-queue-kind">{item.label}</span>
                <span className="forge-queue-detail">{item.detail}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
      {queue.length === 0 && (
        <p className="muted">Queue is clear — nothing suggested beyond the head action.</p>
      )}
    </section>
  );
}
