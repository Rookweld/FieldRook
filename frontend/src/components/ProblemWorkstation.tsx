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
import { ResolutionWorkspace } from "./ResolutionWorkspace";
import { WorkedBefore } from "./WorkedBefore";
import { DiagnosisPanel } from "./DiagnosisPanel";
import { resolutionOf } from "./WorkflowStage";
import { EvidenceCards } from "./EvidenceCards";
import { EvidencePeek } from "./EvidencePeek";
import { SignalScope } from "./SignalScope";
import {
  OverviewPanel,
  type InvestigationView,
  type NextAction,
} from "./OverviewPanel";
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

/**
 * Honest pending state for blocking backend requests. The backend reports
 * no intermediate phases, so this shows elapsed time and sets expectations
 * instead of inventing progress the server never sent.
 */
function PendingPanel({ what }: { what: string }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="pending" role="status" aria-live="polite">
      <SignalScope width={132} active />
      <div>
        <p>{what}</p>
        <p>
          <span className="pending-elapsed">{elapsed}s elapsed</span>{" "}
          <span className="muted">
            — live-model investigations usually take 15–45 seconds. The page updates when
            the assessment arrives; nothing here runs ahead of the server.
          </span>
        </p>
      </div>
    </div>
  );
}

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
  const [view, setView] = useState<InvestigationView>("findings");

  // Drives the per-view ambient tint on the environment. Purely
  // decorative; App.tsx owns the attribute for non-problem tabs.
  useEffect(() => {
    document.querySelector(".app")?.setAttribute("data-view", view);
    return () => {
      document.querySelector(".app")?.removeAttribute("data-view");
    };
  }, [view]);
  const [pendingFocus, setPendingFocus] = useState<string | null>(null);
  const [pendingScroll, setPendingScroll] = useState<string | null>(null);

  useEffect(() => {
    if (initial) {
      setInvestigation(initial);
      setSelectedEvidence(null);
      setError(null);
      setView("findings");
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

  // Deliberate navigation only: focus/scroll land after the view renders.
  useEffect(() => {
    if (!pendingFocus) return;
    const id = pendingFocus;
    setPendingFocus(null);
    const timer = setTimeout(() => {
      document.getElementById(id)?.focus({ preventScroll: false });
    }, 50);
    return () => clearTimeout(timer);
  }, [pendingFocus, view]);

  useEffect(() => {
    if (!pendingScroll) return;
    const id = pendingScroll;
    setPendingScroll(null);
    const timer = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ block: "nearest" });
    }, 50);
    return () => clearTimeout(timer);
  }, [pendingScroll, view]);

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
      setView("findings");
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

  const gotoEvidence = useCallback((id: string) => {
    setSelectedEvidence(null);
    setView("evidence");
    setPendingScroll(`evcard-${id}`);
  }, []);

  const runNextAction = useCallback((action: NextAction) => {
    setView(action.view);
    if (action.focusId) setPendingFocus(action.focusId);
  }, []);

  const startNew = useCallback(() => {
    setInvestigation(null);
    setSelectedEvidence(null);
    setError(null);
    setView("findings");
  }, []);

  return (
    <>
      {error && (
        <div className="card error" role="alert">
          <div>
            <strong>Error.</strong> <span>{error}</span>
          </div>
        </div>
      )}

      {!investigation ? (
        <section className="card surface-hero">
          <div className="hero">
            <div className="hero-copy">
              <h2>Name the symptom.</h2>
              <p className="lede">
                FieldRook runs read-only Windows diagnostics, cites every claim to
                timestamped evidence, and verifies fixes by measurement — never by
                assumption.
              </p>
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
          <details className="advanced">
            <summary>Advanced: fixture mode (development and demos)</summary>
            <label className="check">
              <input
                type="checkbox"
                checked={useFixtures}
                onChange={(e) => setUseFixtures(e.target.checked)}
                disabled={busy !== null}
              />
              <span>Force fixture data</span>
            </label>
          </details>
          {busy === "investigating" && (
            <PendingPanel what="Investigating — the problem is with the analysis engine, which may call several read-only diagnostic tools." />
          )}
            </div>
            <div className="core-stage" aria-hidden="true">
              <div className="core-idle">
                <SignalScope width={264} active={busy === "investigating"} />
              </div>
              <p className="core-caption">
                Signal scope · {busy === "investigating" ? "active" : "standby"}
              </p>
            </div>
          </div>
        </section>
      ) : (
        <>
          <div className="contextbar">
            <p className="contextbar-problem" title={investigation.problem}>
              {investigation.problem}
            </p>
            <span className="contextbar-meta">
              {investigation.investigation_id} ·{" "}
              {new Date(investigation.created_at).toLocaleString()} · {investigation.status}
            </span>
            <span className="contextbar-spacer" />
            <button type="button" className="button button-ghost button-small" onClick={startNew}>
              New investigation
            </button>
          </div>

          <EvidencePeek
            evidence={investigation.evidence}
            selectedId={selectedEvidence}
            onClose={() => setSelectedEvidence(null)}
            onNavigate={gotoEvidence}
          />

          <nav className="views" aria-label="Investigation views">
            <button
              type="button"
              role="tab"
              aria-selected={view === "findings"}
              className="view-tab"
              onClick={() => setView("findings")}
            >
              Findings
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === "evidence"}
              className="view-tab"
              onClick={() => setView("evidence")}
            >
              Evidence <span className="view-count">{investigation.evidence.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === "resolve"}
              className="view-tab"
              onClick={() => setView("resolve")}
            >
              Resolve
              {(() => {
                const tone = resolutionOf(investigation).tone;
                return tone === "mute" ? null : (
                  <span
                    className={`view-dot view-dot-${tone === "good" ? "good" : tone === "bad" ? "bad" : "warn"}`}
                    aria-hidden="true"
                  />
                );
              })()}
            </button>
          </nav>

          {view === "findings" && (
            <div className="view-panel">
              <OverviewPanel
                investigation={investigation}
                onEvidenceClick={setSelectedEvidence}
                onOpenEvidence={() => setView("evidence")}
                onAction={runNextAction}
              />
              <ProgressPanel
                investigation={investigation}
                onEvidenceClick={setSelectedEvidence}
                onReverify={(id) => void reverify(id)}
                busy={busy !== null}
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
              <WorkedBefore
                investigation={investigation}
                onUpdate={setInvestigation}
                onEvidenceClick={setSelectedEvidence}
              />
              <section className="card">
                <div className="card-head">
                  <h2>Follow-up</h2>
                  <span className="muted">continues this investigation</span>
                </div>
                <label className="field">
                  <span>Ask for more evidence or clarification</span>
                  <textarea
                    id="followup-input"
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
                {busy === "followup" && (
                  <PendingPanel what="Asking a follow-up — the analysis engine is working with the evidence collected so far." />
                )}
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
            </div>
          )}

          {view === "evidence" && (
            <div className="view-panel">
              <EvidenceCards
                evidence={investigation.evidence}
                selectedId={selectedEvidence}
                onSelect={setSelectedEvidence}
                refreshes={investigation.refreshes}
                onReverify={(id) => void reverify(id)}
                reverifyingId={reverifyingId}
                reverifyDisabled={busy !== null}
              />
              <RefreshPanel refreshes={investigation.refreshes} onEvidenceClick={setSelectedEvidence} />
              <Timeline activity={investigation.activity} onEvidenceClick={setSelectedEvidence} />
            </div>
          )}

          {view === "resolve" && (
            <div className="view-panel">
              <ActionCenter investigation={investigation} onUpdate={setInvestigation} />
              <ResolutionWorkspace
                investigation={investigation}
                onUpdate={setInvestigation}
                onEvidenceClick={setSelectedEvidence}
              />
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
            </div>
          )}
        </>
      )}
    </>
  );
}
