import { useState } from "react";
import type { InvestigationResponse } from "../types";
import { fetchInvestigationExport } from "../api";
import { caseDispositionLabel, hasRecordedVerifiedResolution } from "../casePresentation";
import { useExport } from "../signalforge/hooks/useExport";
import "./CaseReportCard.css";

function handoffSummary(inv: InvestigationResponse): string {
  const measured = hasRecordedVerifiedResolution(inv);
  return [
    "FieldRook — technician handoff",
    `Case: ${inv.investigation_id}`,
    `Reported problem: ${inv.problem}`,
    `Case filing: ${caseDispositionLabel(inv.disposition)}`,
    `Technical resolution: ${measured ? "Verified resolved in recorded verification" : "Not recorded as verified resolved"}`,
    `Evidence records: ${inv.evidence.length} (${inv.uses_fixtures ? "includes simulated/fixture observations" : "collected evidence"})`,
    `Filed at: ${inv.closed_at ? new Date(inv.closed_at).toLocaleString() : "Not filed"}`,
    `Technician filing note: ${inv.closure_note?.trim() || "No filing note"}`,
    "",
    "Technician filing and diagnostic-model interpretation are not proof of a verified repair.",
    "Export the full FieldRook report for evidence, history and source references.",
  ].join("\n");
}

/** One consistent report surface: native Save As in FieldRook Desktop,
 * browser download elsewhere; the full report is fetched only on request. */
export function CaseReportCard({ investigation }: { investigation: InvestigationResponse }) {
  const { busy, error: exportError, downloadInvestigation, clearError } = useExport();
  const [preview, setPreview] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const verified = hasRecordedVerifiedResolution(investigation);
  const id = investigation.investigation_id;

  async function loadPreview(): Promise<void> {
    if (preview !== null || previewBusy) return;
    setPreviewBusy(true);
    setPreviewError(null);
    try {
      setPreview(await fetchInvestigationExport(id, "markdown"));
    } catch (cause) {
      setPreviewError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setPreviewBusy(false);
    }
  }

  async function copyHandoff(): Promise<void> {
    setCopied(false);
    setCopyError(null);
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard permission is unavailable in this window.");
      }
      await navigator.clipboard.writeText(handoffSummary(investigation));
      setCopied(true);
    } catch (cause) {
      setCopyError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <section className="card fr-report" aria-label="Case report" data-testid="case-report">
      <div className="card-head">
        <h2>Case report</h2>
        <span className="badge">{id}</span>
      </div>
      <p className="muted">
        Save a complete evidence-linked report for a ticket, handoff or your own records.
        Full exports include the case timeline, technician notes and investigation details.
      </p>
      <dl className="fr-report-summary">
        <div><dt>Case filing</dt><dd>{caseDispositionLabel(investigation.disposition)}</dd></div>
        <div>
          <dt>Technical verification</dt>
          <dd className={verified ? "fr-report-verified" : "fr-report-caution"}>
            {verified ? "Verified resolved in recorded checks" : "No verified resolution recorded"}
          </dd>
        </div>
        <div><dt>Evidence</dt>
          <dd>{investigation.evidence.length} records · {investigation.uses_fixtures ? "fixture/simulated" : "collected"}</dd>
        </div>
      </dl>
      <div className="fr-report-actions">
        <button type="button" className="button" disabled={busy !== null}
          onClick={() => { clearError(); void downloadInvestigation(id, "markdown"); }}>
          {busy === "investigation-markdown" ? "Saving report…" : "Save report (.md)"}
        </button>
        <button type="button" className="button button-ghost" disabled={busy !== null}
          onClick={() => { clearError(); void downloadInvestigation(id, "json"); }}>
          {busy === "investigation-json" ? "Saving data…" : "Export data (.json)"}
        </button>
        <button type="button" className="button button-ghost"
          onClick={() => void copyHandoff()}>
          Copy ticket handoff
        </button>
      </div>
      {copied && <p className="fr-report-notice" role="status">Ticket summary copied to clipboard.</p>}
      {copyError && <p className="fr-report-error" role="alert">Copy failed: {copyError}</p>}
      {exportError && <p className="fr-report-error" role="alert">{exportError}</p>}
      <details className="fr-report-preview" onToggle={(event) => {
        if (event.currentTarget.open) void loadPreview();
      }}>
        <summary>Preview full Markdown report</summary>
        {previewBusy && <p className="muted" role="status">Loading report from the local service…</p>}
        {previewError && (
          <div>
            <p role="alert" className="fr-report-error">{previewError}</p>
            <button type="button" className="button button-ghost"
              onClick={() => void loadPreview()}>Retry preview</button>
          </div>
        )}
        {preview !== null && (
          <pre className="fr-report-text" tabIndex={0} aria-label="Full report text">
            {preview}
          </pre>
        )}
      </details>
      <p className="fr-report-footnote">
        A technician-reported resolution is not automatically a measured fix.
        Review source provenance before sharing the report outside your organization.
      </p>
    </section>
  );
}
