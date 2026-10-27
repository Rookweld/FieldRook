import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  addInvestigationNote,
  followUpInvestigation,
  listServices,
  reverifyEvidence,
  startInvestigation,
} from "../api";
import type { InvestigationResponse, ServiceSummary } from "../types";
import { ActionCenter } from "./ActionCenter";
import { DiagnosisPanel } from "./DiagnosisPanel";
import { StageStepper, resolutionOf, stageOf } from "./WorkflowStage";
import { EvidenceCards } from "./EvidenceCards";
import { OverviewPanel } from "./OverviewPanel";
import { ProgressPanel } from "./ProgressPanel";
import { RefreshPanel } from "./RefreshPanel";
import { Timeline } from "./Timeline";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

const PRESETS: { id: string; label: string; template: string }[] = [
  {
    id: "app",
    label: "Application problem",
    template:
      "The application <name> <crashes on launch / freezes / shows an error>.\nWhat happens: \nWhen it started: \nExact error text or code: ",
  },
  {
    id: "network",
    label: "Network problem",
    template:
      "Network problem: <no connectivity / VPN drops / DNS fails>.\nWhat happens: \nWired or Wi-Fi: \nAffected sites or hosts: ",
  },
  {
    id: "windows",
    label: "Windows / background process",
    template:
      "Windows background problem: <recurring window / service issue / scheduled task>.\nWhat happens: \nHow often: \nWhen it started: ",
  },
];

export function ProblemWorkstation({
  initial,
}: {
  initial?: InvestigationResponse | null;
}) {
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [problem, setProblem] = useState<string>("");
  const [serviceName, setServiceName] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [consent, setConsent] = useState<boolean>(false);
  const [useFixtures, setUseFixtures] = useState<boolean>(false);
  const [busy, setBusy] = useState<null | "investigating" | "followup" | "note" | "reverify">(null);
  const [reverifyingId, setReverifyingId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState<string>("");
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(
    initial ?? null,
  );

  useEffect(() => {
    if (initial) {
      setInvestigation(initial);
      setSelectedEvidence(null);
      setError(null);
    }
  }, [initial]);
  const [followup, setFollowup] = useState<string>("");
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    listServices().then(
      (svc) => {
        if (!cancelled) setServices(svc.services);
      },
      () => {
        /* service list is optional; the investigation works without it */
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const clearFile = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    if (fileInput.current) fileInput.current.value = "";
  }, [previewUrl]);

  const onFileChange = (input: HTMLInputElement) => {
    const picked = input.files?.[0] ?? null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (!picked) {
      setFile(null);
      setPreviewUrl(null);
      return;
    }
    if (picked.size > MAX_FILE_BYTES) {
      setError("Screenshot exceeds the 5MB limit.");
      setFile(null);
      setPreviewUrl(null);
      input.value = "";
      return;
    }
    setFile(picked);
    setPreviewUrl(URL.createObjectURL(picked));
  };

  const investigate = useCallback(async (): Promise<void> => {
    if (!problem.trim() || busy) return;
    if (file && !consent) {
      setError(
        "Sharing consent is required to send the screenshot to the Meta API — check the consent box or remove the image.",
      );
      return;
    }
    setError(null);
    setInvestigation(null);
    setSelectedEvidence(null);
    setBusy("investigating");
    try {
      const result = await startInvestigation({
        problem: problem.trim(),
        serviceName: serviceName || undefined,
        useFixtures: useFixtures ? true : undefined,
        shareConsent: consent,
        screenshot: file,
      });
      setInvestigation(result);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Request failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(null);
    }
  }, [problem, serviceName, file, consent, useFixtures, busy]);

  const sendFollowup = useCallback(async (): Promise<void> => {
    if (!investigation || !followup.trim() || busy) return;
    setError(null);
    setBusy("followup");
    try {
      const result = await followUpInvestigation(
        investigation.investigation_id,
        followup.trim(),
      );
      setInvestigation(result);
      setFollowup("");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Follow-up failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(null);
    }
  }, [investigation, followup, busy]);

  const reverify = useCallback(
    async (evidenceId: string): Promise<void> => {
      if (!investigation || busy) return;
      setError(null);
      setBusy("reverify");
      setReverifyingId(evidenceId);
      try {
        const result = await reverifyEvidence(investigation.investigation_id, evidenceId);
        setInvestigation(result);
        const latest = result.refreshes[result.refreshes.length - 1];
        if (latest?.new_evidence_id) setSelectedEvidence(latest.new_evidence_id);
      } catch (e) {
        if (e instanceof ApiError) {
          setError(`Re-check failed (HTTP ${e.status}): ${e.message}`);
        } else {
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        setBusy(null);
        setReverifyingId(null);
      }
    },
    [investigation, busy],
  );

  const saveNote = useCallback(async (): Promise<void> => {
    if (!investigation || !noteText.trim() || busy) return;
    setError(null);
    setBusy("note");
    try {
      const result = await addInvestigationNote(
        investigation.investigation_id,
        noteText.trim(),
      );
      setInvestigation(result);
      setNoteText("");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Saving note failed (HTTP ${e.status}): ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(null);
    }
  }, [investigation, noteText, busy]);

  return (
    <>
      {error && (
        <div className="card error" role="alert">
          <div>
            <strong>Error.</strong> <span>{error}</span>
          </div>
        </div>
      )}

      <StageStepper stage={stageOf(investigation)} />

      <section className="card">
        <div className="card-head">
          <h2>
            <span className="eyebrow">Stage 1 — Investigate</span>New investigation
          </h2>
          <span className="muted">describe the problem — service optional</span>
        </div>
        <div className="preset-row" role="group" aria-label="Investigation templates">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className="preset-button"
              onClick={() => setProblem(preset.template)}
              disabled={busy !== null}
            >
              {preset.label}
            </button>
          ))}
          <span className="muted">templates — or describe the problem free-form</span>
        </div>
        <label className="field">
          <span>Problem description</span>
          <textarea
            className="problem"
            rows={4}
            maxLength={4000}
            placeholder="My VPN disconnects every 10 minutes. Sometimes Windows says the network adapter is unavailable."
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            disabled={busy !== null}
          />
        </label>
        <div className="controls">
          <label className="field">
            <span>Suspected service (optional)</span>
            <select
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
              disabled={busy !== null}
            >
              <option value="">No specific service</option>
              {services.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.display_name} ({s.name}) — {s.status}
                </option>
              ))}
            </select>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={useFixtures}
              onChange={(e) => setUseFixtures(e.target.checked)}
              disabled={busy !== null}
            />
            <span>Force fixture data</span>
          </label>
          <button
            className="button"
            onClick={() => void investigate()}
            disabled={busy !== null || !problem.trim()}
          >
            {busy === "investigating" ? "Investigating…" : "Investigate"}
          </button>
        </div>
        <div className="file-row">
          <label className="field">
            <span>Screenshot (optional, PNG/JPEG, max 5MB)</span>
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => onFileChange(e.currentTarget)}
              disabled={busy !== null}
            />
          </label>
          {previewUrl && (
            <div className="preview-box">
              <img src={previewUrl} alt="Attached screenshot preview" className="preview" />
              <button type="button" className="link-button" onClick={clearFile}>
                Remove
              </button>
            </div>
          )}
        </div>
        {file && (
          <>
            <label className="check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                disabled={busy !== null}
              />
              <span>I am authorized to share this screenshot with the Meta AI API for analysis.</span>
            </label>
            <p className="warn">
              Screenshots may contain sensitive information. Only attach images you are
              authorized to share. FieldRook does not store screenshots.
            </p>
          </>
        )}
        {busy === "investigating" && (
          <p className="muted">
            Investigating — the model may call several diagnostic tools. Watch the activity
            timeline below.
          </p>
        )}
      </section>

      {investigation && (
        <>
          <section className="card">
            <div className="card-head">
              <h2>
                <span className="eyebrow">Stage 2 — Understand</span>Investigation
              </h2>
              <div className="badges">
                <span className={investigation.uses_fixtures ? "badge badge-sim" : "badge badge-live"}>
                  {investigation.uses_fixtures ? "FIXTURES" : "LIVE DIAGNOSTICS"}
                </span>
                <span className={investigation.analysis_mode === "live" ? "badge badge-live" : "badge badge-sim"}>
                  {investigation.analysis_mode === "live" ? "LIVE MODEL" : "SIMULATED"}
                </span>
                {investigation.has_screenshot && <span className="badge">SCREENSHOT</span>}
              </div>
            </div>
            <p className="muted">
              {investigation.investigation_id} &middot;{" "}
              {new Date(investigation.created_at).toLocaleString()} &middot; status:{" "}
              {investigation.status}
              {investigation.service_name && ` · service: ${investigation.service_name}`}
            </p>
            <p className="quote">{investigation.problem}</p>
            <p className={`resolution resolution-${resolutionOf(investigation).tone}`}>
              {resolutionOf(investigation).label}
            </p>
            {investigation.warnings.map((w, i) => (
              <p key={i} className="warn">
                {w}
              </p>
            ))}
          </section>

          <OverviewPanel investigation={investigation} onEvidenceClick={setSelectedEvidence} />
          <ProgressPanel
            investigation={investigation}
            onEvidenceClick={setSelectedEvidence}
            onReverify={(id) => void reverify(id)}
            busy={busy !== null}
          />
          <RefreshPanel refreshes={investigation.refreshes} onEvidenceClick={setSelectedEvidence} />
          <Timeline activity={investigation.activity} />
          <EvidenceCards
            evidence={investigation.evidence}
            selectedId={selectedEvidence}
            onSelect={setSelectedEvidence}
            refreshes={investigation.refreshes}
            onReverify={(id) => void reverify(id)}
            reverifyingId={reverifyingId}
            reverifyDisabled={busy !== null}
          />
          {investigation.assessment && (
            <DiagnosisPanel
              analysis={investigation.assessment}
              incidentId={investigation.investigation_id}
              createdAt={investigation.created_at}
              warnings={[]}
              onEvidenceClick={setSelectedEvidence}
            />
          )}

          <ActionCenter investigation={investigation} onUpdate={setInvestigation} />

          <section className="card">
            <div className="card-head">
              <h2>Report export</h2>
              <div className="history-links">
                <a
                  className="link-button"
                  href={`/api/investigations/${encodeURIComponent(investigation.investigation_id)}/export?format=markdown`}
                >
                  Download Markdown
                </a>
                <a
                  className="link-button"
                  href={`/api/investigations/${encodeURIComponent(investigation.investigation_id)}/export?format=json`}
                >
                  Download JSON
                </a>
              </div>
            </div>
            <p className="muted">
              Ticket-ready report: summary, timeline, evidence, proposals, approvals, execution
              records, and the verified outcome.
            </p>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Technician notes</h2>
              <span className="muted">
                {investigation.notes.length} saved &middot; included in exports
              </span>
            </div>
            {investigation.notes.length === 0 && (
              <p className="muted">
                No notes yet. Record onsite observations, user statements, or comparisons
                between investigation rounds.
              </p>
            )}
            <ul className="notes">
              {investigation.notes.map((note) => (
                <li key={note.note_id}>
                  <span className="muted">{new Date(note.created_at).toLocaleString()}</span>
                  <p>{note.text}</p>
                </li>
              ))}
            </ul>
            <label className="field">
              <span>Add a note</span>
              <textarea
                className="problem"
                rows={2}
                maxLength={2000}
                placeholder="14:05 — user showed the error dialog; screenshot attached to the ticket."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                disabled={busy !== null}
              />
            </label>
            <div className="controls">
              <button
                className="button"
                onClick={() => void saveNote()}
                disabled={busy !== null || !noteText.trim()}
              >
                {busy === "note" ? "Saving…" : "Save note"}
              </button>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Follow-up</h2>
              <span className="muted">continues this investigation</span>
            </div>
            <label className="field">
              <span>Ask for more evidence or clarification</span>
              <textarea
                className="problem"
                rows={2}
                maxLength={2000}
                placeholder="Check whether the network adapter recently disconnected."
                value={followup}
                onChange={(e) => setFollowup(e.target.value)}
                disabled={busy !== null}
              />
            </label>
            <div className="controls">
              <button
                className="button"
                onClick={() => void sendFollowup()}
                disabled={busy !== null || !followup.trim()}
              >
                {busy === "followup" ? "Asking…" : "Send follow-up"}
              </button>
            </div>
          </section>
        </>
      )}
    </>
  );
}
