import { type ReactNode } from "react";
import type { InvestigationResponse } from "../../types";
import { caseDispositionLabel } from "../../casePresentation";
import type { WorkbenchProps } from "../types";

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

/** Show a compact title; never discard the actual technician report. */
function caseHeadline(problem: string): { title: string; shortened: boolean } {
  const report = problem.trim().replace(/\s+/g, " ");
  const firstSentence = report.match(/^.{28,130}?[.!?](?=\s|$)/)?.[0] ?? "";
  let title = firstSentence || report;
  if (title.length > 130) {
    const slice = title.slice(0, 127);
    const boundary = slice.lastIndexOf(" ");
    title = (boundary >= 74 ? slice.slice(0, boundary) : slice).trim() + "…";
  }
  return { title, shortened: title !== report };
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
  onOpenResolve,
  children,
}: WorkbenchProps & { children: ReactNode }) {
  if (!investigation) {
    return (
      <section className="sf-screen" aria-label="Workbench">
        {/* Keep a first DOM sibling in both branches so React preserves
            the keyed engine when intake becomes an active investigation. */}
        <div className="sf-hero-placeholder" aria-hidden="true" />
        <div className="sf-work-content sf-work-content-intake">
          <div className="sf-intake-heading">
            <div>
              <span className="sf-section-label">NEW INVESTIGATION</span>
              <p>Describe the issue to start. Need an older case?{" "}
                <button type="button" className="sf-inline-link" onClick={onGoLaunchpad}>Open history</button>.
              </p>
              <span className="sf-minihelp">
                {status ? (status.model_mode === "live"
      ? "Default: live AI · select a provider under Advanced"
      : "Default: simulation · select local AI under Advanced") : "Service unavailable — check Settings"}
              </span>
            </div>
            <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onImport}>
              Import package
            </button>
          </div>
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
  const headline = caseHeadline(investigation.problem);

  return (
    <section className="sf-screen" aria-label="Workbench">
      <div className="sf-hero sf-hero-case">
        <div className="sf-hero-head">
          <span className="sf-hero-chip">
            {investigation.disposition && investigation.disposition !== "open"
              ? `FILED · ${caseDispositionLabel(investigation.disposition, true)}`
              : investigation.stage.replace(/_/g, " ")}
          </span>
          <span className="sf-hero-id">
            CASE · {investigation.investigation_id.slice(0, 8)} · {targetLabel(investigation)}
          </span>
        </div>
        <p className="sf-hero-eyebrow">REPORTED SYMPTOM</p>
        <h1 id="sf-case-headline" title={headline.shortened ? investigation.problem : undefined}>
          {headline.title}
        </h1>
        <div className="sf-hero-details">
          <span>{new Date(investigation.created_at).toLocaleString()}</span>
          <span>{investigation.analysis_mode === "live"
            ? (investigation.model.startsWith("local/") ? "Local AI analysis" : "Live AI analysis")
            : "Simulated analysis"}</span>
          <span>{investigation.uses_fixtures ? "Fixture evidence" : investigation.evidence.length + " evidence records"}</span>
          {steps.length > 0 && <span>{done}/{steps.length} plan steps recorded</span>}
        </div>
        {headline.shortened && (
          <details className="sf-case-original">
            <summary>Read the full problem report</summary>
            <p>{investigation.problem}</p>
          </details>
        )}
      </div>
      <div className="sf-work-content">
        {investigation.disposition && investigation.disposition !== "open" ? (
          <div className="sf-case-filed" role="status">
            This case is filed as <strong>{caseDispositionLabel(investigation.disposition)}</strong>.
            <button type="button" className="sf-inline-link" onClick={onOpenResolve}>
              Review filing or reopen ↗
            </button>
          </div>
        ) : (
          <NextPanel investigation={investigation} onOpenGuide={onOpenGuide} />
        )}
        <details className="sf-deep-dive">
          <summary>Case context &amp; recent activity</summary>
          <div className="sf-deep-dive-content">
            <div className="sf-twins">
              <HypothesisTile investigation={investigation} />
              <ObservationsTile investigation={investigation} />
            </div>
            <HappenedStrip investigation={investigation} onGoEvidence={onGoEvidence} />
          </div>
        </details>
        <div className="sf-case-actions" aria-label="Investigation shortcuts">
          <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={() => onGoNotes("")}>
            + Add technician note
          </button>
          <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoEvidence}>
            Review evidence ↗
          </button>
          <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onImport}>
            Import package
          </button>
          <button type="button" className="sf-inline-link" onClick={onNew}>
            New case
          </button>
        </div>
        {/* Same stable key as the no-case branch above (BLOCKER-1). */}
        <section key="sf-engine" className="sf-engine" aria-label="Investigation workspace">
          {children}
        </section>
      </div>
    </section>
  );
}
