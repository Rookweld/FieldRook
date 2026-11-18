import { useState } from "react";
import { setCaseDisposition } from "../api";
import type { CaseDisposition, InvestigationResponse } from "../types";
import "./CaseDispositionCard.css";

const LABELS: Record<CaseDisposition, string> = {
  open: "Open",
  resolved: "Resolved · technician-reported",
  needs_followup: "Waiting for follow-up",
  handed_off: "Handed off",
};

type FilingChoice = Exclude<CaseDisposition, "open">;

export function CaseDispositionCard({
  investigation,
  onUpdate,
}: {
  investigation: InvestigationResponse;
  onUpdate: (next: InvestigationResponse) => void;
}) {
  const [choice, setChoice] = useState<FilingChoice>("resolved");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const current = investigation.disposition ?? "open";
  const filed = current !== "open";
  const verified = investigation.plans.some(
    (plan) => plan.status === "VERIFIED_RESOLVED",
  ) || investigation.proposals.some(
    (proposal) => proposal.status === "VERIFIED_RESOLVED",
  );

  const change = async (next: CaseDisposition, reason: string) => {
    if (saving) return;
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      const updated = await setCaseDisposition(investigation.investigation_id, next, reason);
      onUpdate(updated);
      if (next === "open") {
        setNotice("Case reopened. Previous filing notes remain in the record.");
      } else {
        setNote("");
        setNotice("Case filing saved with your note and timestamp.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card fr-case-disposition" aria-label="Case status" data-testid="case-disposition">
      <div className="card-head">
        <h2>Case status</h2>
        <span className={filed ? "badge" : "badge badge-sim"}>{LABELS[current]}</span>
      </div>
      <p className="muted">
        File this investigation when your work is done for now. Filing is a technician
        decision; it does not turn an unverified fix into measured proof.
      </p>
      {filed ? (
        <div className="fr-filing-result">
          <p><strong>{LABELS[current]}</strong>
            {investigation.closed_at && (
              <span className="muted"> · {new Date(investigation.closed_at).toLocaleString()}</span>
            )}
          </p>
          <p className="fr-filing-note">{investigation.closure_note || "No filing note available."}</p>
          <div className="fr-filing-actions">
            <button type="button" className="button" disabled={saving}
                    onClick={() => void change("open", "")}>
              {saving ? "Reopening…" : "Reopen case"}
            </button>
            <a href={`/api/investigations/${encodeURIComponent(investigation.investigation_id)}/export?format=markdown`}>
              Download case report ↗
            </a>
          </div>
        </div>
      ) : (
        <form className="fr-filing-form" onSubmit={(event) => {
          event.preventDefault();
          if (!note.trim()) {
            setError("Record what was done, what remains, or who is taking over.");
            return;
          }
          void change(choice, note.trim());
        }}>
          <label className="field">
            <span>What happens to this case?</span>
            <select value={choice}
                    onChange={(event) => setChoice(event.target.value as FilingChoice)}
                    disabled={saving}>
              <option value="resolved">Resolved · technician-reported</option>
              <option value="needs_followup">Waiting for follow-up</option>
              <option value="handed_off">Handed off to another technician</option>
            </select>
          </label>
          <label className="field">
            <span>Technician's filing note (required)</span>
            <textarea rows={3} maxLength={2000} value={note} disabled={saving}
              onChange={(event) => setNote(event.target.value)}
              placeholder="What was done? What is the remaining issue? Who owns the next step?" />
          </label>
          {choice === "resolved" && !verified && (
            <p className="fr-verification-notice">
              No verified fix is recorded. You can still file this as technician-reported
              resolved, but the report will not claim an independently verified outcome.
            </p>
          )}
          <button type="submit" className="button" disabled={saving || !note.trim()}>
            {saving ? "Saving…" : "Save case status"}
          </button>
        </form>
      )}
      {error && <p className="warn" role="alert">{error}</p>}
      {notice && <p className="muted" role="status">{notice}</p>}
    </section>
  );
}
