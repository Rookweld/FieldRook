import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  deleteKnowledgeEntry,
  knowledgeExportUrl,
  listKnowledge,
} from "../api";
import type { KnowledgeEntry } from "../types";

const OUTCOME_CLASS: Record<string, string> = {
  VERIFIED_RESOLVED: "badge badge-verified",
  NOT_RESOLVED: "badge badge-fail",
  INCONCLUSIVE: "badge",
  UNRESOLVED: "badge",
};

const CATEGORIES = [
  "",
  "demo-worker",
  "services",
  "network",
  "network-dns",
  "applications",
  "scheduled-tasks",
  "performance",
  "general",
];

const OUTCOMES = ["", "VERIFIED_RESOLVED", "NOT_RESOLVED", "INCONCLUSIVE", "UNRESOLVED"];

function EntryDetail({ entry }: { entry: KnowledgeEntry }) {
  return (
    <div className="knowledge-detail">
      <p className="muted">
        {entry.category} · identity {entry.identity ?? "(none)"} · events{" "}
        {entry.event_codes.join(", ") || "(none)"} · {entry.occurrence_count} occurrence
        {entry.occurrence_count === 1 ? "" : "s"}
      </p>
      <p>
        <span className="runbook-label">Symptoms:</span> {entry.symptoms.join(", ") || "(none)"}
      </p>
      <p>
        <span className="runbook-label">Cause:</span> {entry.root_cause ?? "(not established)"}{" "}
        {entry.root_cause_verified ? "(technician-confirmed)" : "(inferred hypothesis)"}
      </p>
      <p>
        <span className="runbook-label">Previously:</span> {entry.intervention || "(none)"}{" "}
        <span className="muted">[{entry.intervention_kind}]</span>
      </p>
      {entry.criteria.length > 0 && (
        <ul className="unverified">
          {entry.criteria.map((c) => (
            <li key={c.criterion_id}>
              <span className="tag tag-inf">CRITERION</span>{" "}
              <span>
                {c.description} ({c.tool_name} {c.path} {c.op}{" "}
                {typeof c.expected === "string" ? c.expected : JSON.stringify(c.expected)};
                before {JSON.stringify(entry.baseline_values[c.criterion_id] ?? null)} →
                after {JSON.stringify(entry.verified_values[c.criterion_id] ?? null)})
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="muted">
        Source: {entry.source_investigation_id}
        {entry.source_plan_id ? ` / ${entry.source_plan_id}` : ""} · evidence{" "}
        {entry.source_evidence_ids.join(", ")} · recorded{" "}
        {new Date(entry.created_at).toLocaleString()}
      </p>
      <div className="controls">
        <a className="link-button" href={knowledgeExportUrl(entry.entry_id, "markdown")} download>
          Export markdown
        </a>
        <a className="link-button" href={knowledgeExportUrl(entry.entry_id, "json")} download>
          Export JSON
        </a>
      </div>
    </div>
  );
}

export function KnowledgeLibrary() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [outcome, setOutcome] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // M010-9: debounce free-text search so typing does not hit the API per keystroke.
  const [debouncedQ, setDebouncedQ] = useState(q);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(timer);
  }, [q]);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setEntries(await listKnowledge({ q: debouncedQ, category, outcome }));
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [debouncedQ, category, outcome]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = async (entryId: string) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await deleteKnowledgeEntry(entryId);
      setOpen((prev) => (prev === entryId ? null : prev));
      await refresh();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Delete failed (HTTP ${e.status}): ${e.message}`);
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
        <h2>Knowledge library</h2>
        <span className="muted">
          {entries.length} remembered incident{entries.length === 1 ? "" : "s"} · local SQLite
          only · redacted signatures
        </span>
      </div>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      <div className="controls">
        <input
          type="search"
          className="mono manual-input"
          placeholder="Search problems, symptoms, identity…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={200}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c === "" ? "All categories" : c}
            </option>
          ))}
        </select>
        <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
          {OUTCOMES.map((o) => (
            <option key={o} value={o}>
              {o === "" ? "All outcomes" : o}
            </option>
          ))}
        </select>
      </div>
      {!loaded && <p className="muted">Loading…</p>}
      {loaded && entries.length === 0 && (
        <p className="muted">
          Nothing remembered yet. Resolve an investigation, then “Save to knowledge”.
        </p>
      )}
      <ul className="rechecks">
        {entries.map((entry) => (
          <li key={entry.entry_id} className="recheck">
            <div className="cause-head">
              <button
                type="button"
                className="link-button knowledge-title"
                onClick={() => setOpen((prev) => (prev === entry.entry_id ? null : entry.entry_id))}
              >
                {entry.problem}
              </button>
              <span className={OUTCOME_CLASS[entry.outcome] ?? "badge"}>{entry.outcome}</span>
              <span className="muted mono">{entry.entry_id}</span>
              <button
                type="button"
                className="link-button"
                disabled={busy}
                onClick={() => void remove(entry.entry_id)}
                title="Delete this local entry"
              >
                Delete
              </button>
            </div>
            {open === entry.entry_id && <EntryDetail entry={entry} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
