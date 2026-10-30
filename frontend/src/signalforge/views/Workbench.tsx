import { useState, type ReactNode } from "react";
import type { InvestigationResponse } from "../../types";
import type { WorkbenchProps } from "../types";
import { RookFigure } from "../components/Shell";
import "./Workbench.css";

function targetLabel(inv: InvestigationResponse): string {
  switch (inv.target) {
    case "local":
      return "This computer";
    case "remote":
      return "Another computer";
    case "unknown":
      return "Target not set";
    default: {
      const _exhaustive: never = inv.target;
      return _exhaustive;
    }
  }
}

function NextPanel({ investigation, onOpenGuide }: { investigation: InvestigationResponse; onOpenGuide: () => void }) {
  const steps = investigation.plan?.steps ?? [];
  const current =
    investigation.plan?.current_step_id != null
      ? (steps.find((step) => step.step_id === investigation.plan?.current_step_id) ?? null)
      : null;
  const position = current ? steps.findIndex((step) => step.step_id === current.step_id) + 1 : 0;
  const openQuestion = investigation.questions.find((question) => question.status === "open") ?? null;

  let index = "—";
  let title = "No suggested step right now";
  let desc = "The investigation has no current plan step or open question. Use the Guide for the full picture.";
  let why: string | null = null;
  let kind: string | null = null;
  if (investigation.blocked_reason) {
    title = "Blocked";
    desc = investigation.blocked_reason;
  } else if (current) {
    index = String(position).padStart(2, "0");
    title = current.instruction;
    desc = `Expected: ${current.expected_observations.length > 0 ? current.expected_observations.join("; ") : "not stated"}`;
    why = current.why;
    kind = current.kind.replace(/_/g, " ");
  } else if (openQuestion) {
    title = openQuestion.question;
    desc = "Answering unblocks the next diagnostic step.";
    why = openQuestion.why;
    kind = "CLARIFYING QUESTION";
  }

  return (
    <div className="sf-next">
      <div className="sf-next-index">
        {index}
        <small>
          NEXT
          <br />
          MOVE
        </small>
      </div>
      <div className="sf-next-text">
        <div className="sf-section-label">↗ NEXT SUGGESTED STEP</div>
        <div className="sf-next-title">{title}</div>
        <div className="sf-next-desc">{desc}</div>
        <div className="sf-next-actions">
          <button type="button" className="sf-btn sf-btn-lime" onClick={onOpenGuide}>
            OPEN GUIDE ↗
          </button>
          {why && (
            <details className="sf-why">
              <summary>WHY THIS STEP? ⓘ</summary>
              <p>{why}</p>
              {kind && <p className="sf-kind">Step kind: {kind}</p>}
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function HypothesisTile({ investigation }: { investigation: InvestigationResponse }) {
  const active = investigation.hypotheses.find((item) => item.status === "active") ?? null;
  const cause = investigation.assessment?.causes[0] ?? null;
  const title = active?.title ?? cause?.title ?? "No hypothesis recorded";
  const note = active
    ? `${active.status} · ${active.supporting_evidence_ids.length} supporting records`
    : cause
      ? `assessed likelihood: ${cause.likelihood} · ${cause.evidence_ids.length} cited records`
      : "Causes are assessed once evidence arrives";

  return (
    <div className="sf-tile sf-tile-pink">
      <div className="sf-tile-head">
        <span>WORKING HYPOTHESIS</span>
        <b aria-hidden="true">?</b>
      </div>
      <h3>{title}</h3>
      <p>{note}</p>
    </div>
  );
}

function ObservationsTile({ investigation }: { investigation: InvestigationResponse }) {
  const facts = investigation.assessment?.facts.length ?? 0;
  return (
    <div className="sf-tile sf-tile-lime">
      <div className="sf-tile-head">
        <span>OBSERVATIONS</span>
        <b aria-hidden="true">↗</b>
      </div>
      <h3>
        {investigation.evidence.length} evidence · {investigation.notes.length} notes
      </h3>
      <p>
        {facts > 0
          ? `${facts} observed facts cited to records`
          : "Observed facts appear once analysis cites them"}
      </p>
    </div>
  );
}

function HappenedStrip({
  investigation,
  onGoEvidence,
}: {
  investigation: InvestigationResponse;
  onGoEvidence: () => void;
}) {
  const recent = investigation.activity.slice(-3).reverse();
  return (
    <section className="sf-happened" aria-label="Latest activity">
      <div className="sf-section-label">◷ WHAT HAPPENED</div>
      {recent.length === 0 ? (
        <p className="sf-minihelp">No activity recorded yet on this case.</p>
      ) : (
        <ol>
          {recent.map((record) => (
            <li key={record.seq}>
              <strong>{record.title}</strong>
              {record.detail && <span> — {record.detail}</span>}
            </li>
          ))}
        </ol>
      )}
      <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoEvidence}>
        Full timeline in Evidence ↗
      </button>
    </section>
  );
}

export function Workbench({
  investigation,
  status,
  onNew,
  onImport,
  onGoNotes,
  onGoEvidence,
  onGoLaunchpad,
  onOpenGuide,
  children,
}: WorkbenchProps & { children: ReactNode }) {
  const [draft, setDraft] = useState("");

  if (!investigation) {
    return (
      <section className="sf-screen" aria-label="Workbench">
        <div className="sf-hero sf-hero-slim">
          <div className="sf-hero-head">
            <span className="sf-hero-chip">NO ACTIVE CASE</span>
            <span className="sf-hero-id">
              {status
                ? `${status.model_mode === "live" ? "LIVE MODEL" : "SIMULATED MODEL"} · ${status.live_diagnostics_available ? "LIVE DIAGNOSTICS" : "FIXTURES ONLY"}`
                : "CONNECTING TO BACKEND"}
            </span>
          </div>
          <h1>
            NAME THE
            <br />
            SYMPTOM.
          </h1>
          <p className="sf-hero-lede">
            Describe the problem below — the intake form handles suspected services, screenshots,
            and Collector packages. Open a past case from the{" "}
            <button type="button" className="sf-inline-link" onClick={onGoLaunchpad}>
              Launchpad
            </button>
            .
          </p>
          <div className="sf-home-actions">
            <button
              type="button"
              className="sf-btn sf-btn-lime"
              onClick={() => document.getElementById("sf-engine-problem")?.focus()}
            >
              Start below ↓
            </button>
            <button type="button" className="sf-btn sf-btn-dark" onClick={onImport}>
              ⇩ Import Collector package
            </button>
          </div>
        </div>
        <div className="sf-work-content">
          {/*
            BLOCKER-1 (M026 ZETA): this section MUST keep the same key in
            both hero branches. The engine below owns the live case; when
            the mirror flips null->case the branch changes, and without a
            stable key React remounts the engine (fresh intake, orphaned
            server case). Keyed, React moves the DOM node and state survives.
          */}
          <section key="sf-engine" className="sf-engine" aria-label="Investigation workspace">
            {children}
          </section>
        </div>
      </section>
    );
  }

  const steps = investigation.plan?.steps ?? [];
  const done = steps.filter((step) => step.status === "done").length;

  return (
    <section className="sf-screen" aria-label="Workbench">
      <div className="sf-hero">
        <div className="sf-hero-head">
          <span className="sf-hero-chip">{investigation.stage.replace(/_/g, " ")}</span>
          <span className="sf-hero-id">
            CASE · {investigation.investigation_id.slice(0, 8)} · {targetLabel(investigation)}
          </span>
        </div>
        <h1>{investigation.problem}</h1>
        <div className="sf-hero-details">
          <span>{new Date(investigation.created_at).toLocaleString()}</span>
          <span>{investigation.analysis_mode === "live" ? "Live analysis" : "Simulated analysis"}</span>
          <span>
            {investigation.uses_fixtures ? "Fixture data" : "Collected data"}
          </span>
        </div>
        <RookFigure />
        {steps.length > 0 && (
          <div className="sf-gauge" aria-label={`${done} of ${steps.length} plan steps recorded`}>
            <div className="sf-gauge-inner">
              <span className="sf-count">
                {String(done).padStart(2, "0")}/{String(steps.length).padStart(2, "0")}
              </span>
              <span className="sf-caption">
                PLAN STEPS
                <br />
                RECORDED
              </span>
            </div>
          </div>
        )}
      </div>
      <div className="sf-work-content">
        <NextPanel investigation={investigation} onOpenGuide={onOpenGuide} />
        <div className="sf-twins">
          <HypothesisTile investigation={investigation} />
          <ObservationsTile investigation={investigation} />
        </div>
        <HappenedStrip investigation={investigation} onGoEvidence={onGoEvidence} />
        <form
          className="sf-composer"
          onSubmit={(event) => {
            event.preventDefault();
            onGoNotes(draft);
          }}
        >
          <label htmlFor="sf-workbench-note" className="sf-hidden">
            Technician observation
          </label>
          <input
            id="sf-workbench-note"
            maxLength={350}
            autoComplete="off"
            placeholder="↳ Describe what happened after the check…"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button className="sf-btn sf-btn-lime" type="submit">
            CONTINUE IN NOTES ↓
          </button>
        </form>
        <p className="sf-minihelp">
          Quick capture jumps to Technician notes below, where notes save with the case.{" "}
          <button type="button" className="sf-inline-link" onClick={onNew}>
            Start a new investigation
          </button>{" "}
          or{" "}
          <button type="button" className="sf-inline-link" onClick={onImport}>
            import a Collector package
          </button>
          .
        </p>
        {/* Same stable key as the no-case branch above (BLOCKER-1). */}
        <section key="sf-engine" className="sf-engine" aria-label="Investigation workspace">
          {children}
        </section>
      </div>
    </section>
  );
}
