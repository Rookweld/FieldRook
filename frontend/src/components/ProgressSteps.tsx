export type Phase = "idle" | "collecting" | "analyzing" | "done";

const STEPS = ["Collect evidence", "Analyze", "Assessment ready"] as const;

export function ProgressSteps({ phase }: { phase: Phase }) {
  const active =
    phase === "collecting" ? 0 : phase === "analyzing" ? 1 : phase === "done" ? 3 : -1;
  return (
    <ol className="steps">
      {STEPS.map((label, i) => {
        const done = i < active || phase === "done";
        const current = i === active;
        return (
          <li
            key={label}
            className={done ? "step step-done" : current ? "step step-active" : "step"}
          >
            <span className="step-dot" aria-hidden="true" />
            {label}
          </li>
        );
      })}
    </ol>
  );
}
