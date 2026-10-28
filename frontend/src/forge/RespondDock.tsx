import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  ApiError,
  addInvestigationNote,
  followUpInvestigation,
  sendTurn,
} from "../api";
import type { TurnKind } from "../types";
import type { RespondDockProps } from "./types";
import "./forge.css";

/** Composer kinds mirror GuidePanel's turn options exactly. */
const KIND_TABS: { value: TurnKind; label: string }[] = [
  { value: "observation", label: "Observation" },
  { value: "test_result", label: "Test result" },
  { value: "answer", label: "Answer" },
  { value: "correction", label: "Correction" },
  { value: "question", label: "Question" },
];

const MAX_FILE_BYTES = 5 * 1024 * 1024;

/**
 * Turn composer (kind tabs + optional screenshot with consent) plus
 * technician notes. Follow-up compatible: the mode switch sends through
 * `followUpInvestigation` instead of `sendTurn`. Every send returns the
 * full InvestigationResponse, which replaces state via onUpdate.
 * Transport is injectable for lead wiring; defaults call api.ts directly.
 */
export function RespondDock({ investigation, onUpdate, onError, disabled, transport }: RespondDockProps) {
  const [mode, setMode] = useState<"report" | "followup">("report");
  const [kind, setKind] = useState<TurnKind>("observation");
  const [text, setText] = useState("");
  const [questionId, setQuestionId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [busy, setBusy] = useState<null | "turn" | "followup" | "note">(null);
  const [elapsed, setElapsed] = useState(0);
  const [localError, setLocalError] = useState<string | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const invId = investigation.investigation_id;
  const openQuestions = investigation.questions.filter((q) => q.status === "open");
  const locked = disabled === true || busy !== null;

  useEffect(() => {
    if (busy !== "turn" && busy !== "followup") {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 500);
    return () => window.clearInterval(timer);
  }, [busy]);

  const fail = (what: string, e: unknown) => {
    const msg =
      e instanceof ApiError ? `${what} failed (HTTP ${e.status}): ${e.message}` : String(e);
    setLocalError(msg);
    onError?.(msg);
  };

  const onTabKeyDown = (e: KeyboardEvent, index: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const delta = e.key === "ArrowRight" ? 1 : -1;
    const next = (index + delta + KIND_TABS.length) % KIND_TABS.length;
    setKind(KIND_TABS[next].value);
    tabRefs.current[next]?.focus();
  };

  const pickFile = (input: HTMLInputElement) => {
    const picked = input.files?.[0] ?? null;
    if (!picked) {
      setFile(null);
      return;
    }
    if (picked.size > MAX_FILE_BYTES) {
      const msg = "Screenshot exceeds the 5MB limit.";
      setLocalError(msg);
      onError?.(msg);
      setFile(null);
      input.value = "";
      return;
    }
    setFile(picked);
  };

  const sendReport = async () => {
    if (!text.trim() || locked) return;
    if (file && !consent) {
      const msg =
        "Sharing consent is required to send the screenshot — check the consent box or remove the image.";
      setLocalError(msg);
      onError?.(msg);
      return;
    }
    setLocalError(null);
    setBusy("turn");
    try {
      const send = transport?.sendTurn ?? ((a) =>
        sendTurn(invId, {
          kind: a.kind,
          text: a.text,
          questionId: a.questionId,
          shareConsent: a.consent,
          screenshot: a.file,
        }));
      const result = await send({
        kind,
        text: text.trim(),
        questionId: kind === "answer" && questionId ? questionId : null,
        file,
        consent,
      });
      onUpdate(result);
      setText("");
      setFile(null);
      setConsent(false);
      setQuestionId("");
    } catch (e) {
      fail("Turn", e);
    } finally {
      setBusy(null);
    }
  };

  const sendFollowup = async () => {
    if (!text.trim() || locked) return;
    setLocalError(null);
    setBusy("followup");
    try {
      const send = transport?.sendFollowup ?? ((m: string) => followUpInvestigation(invId, m));
      onUpdate(await send(text.trim()));
      setText("");
    } catch (e) {
      fail("Follow-up", e);
    } finally {
      setBusy(null);
    }
  };

  const saveNote = async () => {
    if (!noteText.trim() || locked) return;
    setLocalError(null);
    setBusy("note");
    try {
      const save = transport?.saveNote ?? ((t: string) => addInvestigationNote(invId, t));
      onUpdate(await save(noteText.trim()));
      setNoteText("");
    } catch (e) {
      fail("Saving note", e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card forge-dock" data-testid="forge-respond-dock" aria-label="Respond">
      <div className="card-head">
        <h2>
          <span className="eyebrow">Respond</span>
        </h2>
        <div className="forge-mode" role="group" aria-label="Composer mode">
          <button
            type="button"
            className={mode === "report" ? "preset-button forge-mode-active" : "preset-button"}
            aria-pressed={mode === "report"}
            onClick={() => setMode("report")}
            disabled={locked}
          >
            Report turn
          </button>
          <button
            type="button"
            className={mode === "followup" ? "preset-button forge-mode-active" : "preset-button"}
            aria-pressed={mode === "followup"}
            onClick={() => setMode("followup")}
            disabled={locked}
          >
            Ask follow-up
          </button>
        </div>
      </div>
      {localError && (
        <p className="warn" role="alert">
          {localError}
        </p>
      )}
      {mode === "report" && (
        <div className="forge-kindtabs" role="tablist" aria-label="Turn kind">
          {KIND_TABS.map((opt, i) => (
            <button
              key={opt.value}
              ref={(el) => {
                tabRefs.current[i] = el;
              }}
              type="button"
              role="tab"
              aria-selected={kind === opt.value}
              tabIndex={kind === opt.value ? 0 : -1}
              className={kind === opt.value ? "forge-kindtab forge-kindtab-active" : "forge-kindtab"}
              onClick={() => setKind(opt.value)}
              onKeyDown={(e) => onTabKeyDown(e, i)}
              disabled={locked}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      {mode === "report" && kind === "answer" && openQuestions.length > 0 && (
        <label className="field">
          <span>Answering question</span>
          <select
            value={questionId}
            onChange={(e) => setQuestionId(e.target.value)}
            disabled={locked}
            aria-label="Answering question"
          >
            <option value="">General answer (no question)</option>
            {openQuestions.map((q) => (
              <option key={q.question_id} value={q.question_id}>
                {q.question.slice(0, 80)}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="field">
        <span>{mode === "report" ? "What did you see, try, or want to ask?" : "Ask for more evidence or clarification"}</span>
        <textarea
          id="forge-respond-input"
          className="problem"
          rows={3}
          maxLength={2000}
          placeholder={
            mode === "report"
              ? "Excel opens local files fine — only files from Teams fail."
              : "Check whether the network adapter recently disconnected."
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={locked}
        />
      </label>
      {mode === "report" && (
        <div className="file-row">
          <label className="field">
            <span>Screenshot (optional, PNG/JPEG, max 5MB)</span>
            <input
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => pickFile(e.currentTarget)}
              disabled={locked}
              aria-label="Follow-up screenshot"
            />
          </label>
          {file && (
            <label className="check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                disabled={locked}
              />
              <span>I am authorized to share this screenshot for analysis.</span>
            </label>
          )}
        </div>
      )}
      <div className="controls">
        <button
          type="button"
          className="button"
          id="forge-respond-send"
          onClick={() => void (mode === "report" ? sendReport() : sendFollowup())}
          disabled={locked || !text.trim()}
        >
          {busy === "turn" || busy === "followup"
            ? "Sending…"
            : mode === "report"
              ? "Send to FieldRook"
              : "Send follow-up"}
        </button>
        {(busy === "turn" || busy === "followup") && (
          <span className="muted" role="status">
            Working — elapsed {elapsed.toFixed(0)}s. The page updates when the round completes.
          </span>
        )}
      </div>
      <div className="forge-notes">
        <h3 className="story-head">
          Technician notes{" "}
          <span className="muted">
            ({investigation.notes.length} saved · included in exports)
          </span>
        </h3>
        {investigation.notes.length > 0 && (
          <ul className="notes">
            {investigation.notes.map((note) => (
              <li key={note.note_id}>
                <span className="muted">{new Date(note.created_at).toLocaleString()}</span>
                <p>{note.text}</p>
              </li>
            ))}
          </ul>
        )}
        <label className="field">
          <span>Add a note</span>
          <textarea
            id="forge-note-input"
            className="problem"
            rows={2}
            maxLength={2000}
            placeholder="Onsite observation, user statement, or round comparison."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            disabled={locked}
          />
        </label>
        <div className="controls">
          <button
            type="button"
            className="button button-ghost"
            id="forge-note-save"
            onClick={() => void saveNote()}
            disabled={locked || !noteText.trim()}
          >
            {busy === "note" ? "Saving…" : "Save note"}
          </button>
        </div>
      </div>
    </section>
  );
}
