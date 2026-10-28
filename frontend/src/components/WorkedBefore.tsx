import { useEffect, useState } from "react";
import {
  ApiError,
  fetchKnowledgeMatches,
  followUpInvestigation,
  recheckKnowledgeEntry,
  recordKnowledge,
} from "../api";
import type { InvestigationResponse, KnowledgeMatch } from "../types";
import { EmptyState } from "./EmptyState";
import { EvidenceChip } from "./EvidenceChip";

const OUTCOME_CLASS: Record<string, string> = {
  VERIFIED_RESOLVED: "badge badge-verified",
  NOT_RESOLVED: "badge badge-fail",
  INCONCLUSIVE: "badge",
  UNRESOLVED: "badge",
};

function MatchCard({
  investigation,
  match,
  busy,
  onUpdate,
}: {
  investigation: InvestigationResponse;
  match: KnowledgeMatch;
  busy: boolean;
  onUpdate: (next: InvestigationResponse) => void;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const entry = match.entry;
  const recheckable = entry.outcome === "VERIFIED_RESOLVED" && entry.criteria.length > 0;

  const run = async (key: string, fn: () => Promise<InvestigationResponse>) => {
    if (busy || active) return;
    setActive(key);
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
      setActive(null);
    }
  };

  const hypothesis = () =>
    `Historical case ${entry.entry_id} (${entry.outcome}) resembles this incident: ` +
    `${match.signals.map((s) => s.detail).join(" ")} ` +
    `Check whether its hypothesis applies here: ${entry.root_cause ?? "no recorded cause"}. ` +
    `Differences to account for: ${match.differences.join(" ") || "none noted."}`;

  return (
    <article className="action-card">
      <div className="card-head">
        <h3 className="action-title">{entry.problem}</h3>
        <span className={OUTCOME_CLASS[entry.outcome] ?? "badge"}>{entry.outcome}</span>
      </div>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      <p className="muted">
        {entry.category} · strength {match.strength} · {entry.occurrence_count} occurrence
        {entry.occurrence_count === 1 ? "" : "s"} · from{" "}
        <span className="mono">{entry.source_investigation_id}</span>
        {entry.verified_at ? ` · verified ${new Date(entry.verified_at).toLocaleString()}` : ""}
      </p>
      <p>
        <span className="runbook-label">Why it matched:</span>{" "}
        {match.signals.map((s) => s.detail).join(" ")}
      </p>
      {match.differences.length > 0 && (
        <p className="warn">
          <span className="runbook-label">Differences:</span> {match.differences.join(" ")}
        </p>
      )}
      {match.missing_evidence.length > 0 && (
        <p className="muted">
          <span className="runbook-label">To compare fully:</span>{" "}
          {match.missing_evidence.join(" ")}
        </p>
      )}
      <p>
        <span className="runbook-label">Previously:</span>{" "}
        {entry.intervention || "(no intervention recorded)"}{" "}
        <span className="muted">[{entry.intervention_kind}]</span>
      </p>
      {entry.criteria.length > 0 && (
        <ul className="unverified">
          {entry.criteria.map((c) => (
            <li key={c.criterion_id}>
              <span className="tag tag-inf">CRITERION</span>{" "}
              <span>
                {c.description} ({c.tool_name} {c.path} {c.op}{" "}
                {typeof c.expected === "string" ? c.expected : JSON.stringify(c.expected)})
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="muted">
        Cause: {entry.root_cause ?? "(not established)"}{" "}
        {entry.root_cause_verified ? "(technician-confirmed)" : "(inferred hypothesis — not fact)"}
      </p>
      <div className="controls">
        <button
          type="button"
          className="button button-ghost"
          disabled={busy || active !== null}
          onClick={() =>
            void run("hypothesis", () => followUpInvestigation(investigation.investigation_id, hypothesis()))
          }
          title="Ask FieldRook to check this hypothesis with read-only diagnostics"
        >
          {active === "hypothesis" ? "Investigating…" : "Investigate this hypothesis"}
        </button>
        {recheckable && (
          <button
            type="button"
            className="button button-ghost"
            disabled={busy || active !== null}
            onClick={() =>
              void run("recheck", () =>
                recheckKnowledgeEntry(investigation.investigation_id, entry.entry_id),
              )
            }
            title="Re-run the historical criteria against current state"
          >
            {active === "recheck" ? "Rechecking…" : "Recheck historical criteria"}
          </button>
        )}
      </div>
    </article>
  );
}

export function WorkedBefore({
  investigation,
  onUpdate,
  onEvidenceClick,
}: {
  investigation: InvestigationResponse;
  onUpdate: (next: InvestigationResponse) => void;
  onEvidenceClick?: (id: string) => void;
}) {
  const [matches, setMatches] = useState<KnowledgeMatch[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cause, setCause] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setMatches(null);
    fetchKnowledgeMatches(investigation.investigation_id).then(
      (result) => {
        if (!cancelled) setMatches(result.matches);
      },
      () => {
        if (!cancelled) setMatches([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [investigation.investigation_id, investigation.evidence.length]);

  const save = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const entry = await recordKnowledge(investigation.investigation_id, cause.trim());
      setSaved(
        `Saved as ${entry.entry_id} (${entry.outcome}, ${entry.occurrence_count} occurrence${entry.occurrence_count === 1 ? "" : "s"}).`,
      );
      setCause("");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Save failed (HTTP ${e.status}): ${e.message}`);
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
        <h2>Worked before</h2>
        <span className="muted">similar resolved incidents · reference only, never proof</span>
      </div>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      {matches === null && <p className="muted">Searching the local library…</p>}
      {matches !== null && matches.length === 0 && (
        <EmptyState
          icon="◇"
          title="No similar incidents remembered"
          body="Nothing in the local library matches this case yet. Resolve it and save the outcome below so the next one starts warmer."
        />
      )}
      {matches?.slice(0, 1).map((match) => (
        <MatchCard
          key={match.entry.entry_id}
          investigation={investigation}
          match={match}
          busy={busy}
          onUpdate={onUpdate}
        />
      ))}
      {(matches?.length ?? 0) > 1 && (
        <details className="ev-json">
          <summary>
            {(matches?.length ?? 0) - 1} further historical match
            {(matches?.length ?? 0) - 1 === 1 ? "" : "es"}
          </summary>
          {matches?.slice(1).map((match) => (
            <MatchCard
              key={match.entry.entry_id}
              investigation={investigation}
              match={match}
              busy={busy}
              onUpdate={onUpdate}
            />
          ))}
        </details>
      )}

      {investigation.regression_checks.length > 0 && (
        <>
          <h3>Regression checks</h3>
          {investigation.regression_checks.map((check) => (
            <div
              key={check.check_id}
              className={`resolution resolution-${check.outcome === "CONFIRMED" ? "good" : check.outcome === "REGRESSION" ? "bad" : "warn"}`}
            >
              {check.outcome} — recheck of {check.entry_id} ·{" "}
              {check.results.filter((r) => r.outcome === "pass").length}/{check.results.length}{" "}
              criteria hold · {new Date(check.checked_at).toLocaleString()}{" "}
              {check.evidence_ids.map((eid) => (
                <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
              ))}
            </div>
          ))}
        </>
      )}

      <h3>Remember this incident</h3>
      {saved && <p className="ok">{saved}</p>}
      <div className="controls">
        <input
          type="text"
          className="mono manual-input"
          placeholder="Confirmed root cause (optional, technician-attested)"
          value={cause}
          onChange={(e) => setCause(e.target.value)}
          disabled={busy}
          maxLength={500}
        />
        <button type="button" className="button" disabled={busy} onClick={() => void save()}>
          {busy ? "Saving…" : "Save to knowledge"}
        </button>
      </div>
      <p className="muted">
        Stored locally (SQLite) with redacted signatures. Inferred causes stay labeled as
        hypotheses unless you confirm one above.
      </p>
    </section>
  );
}
