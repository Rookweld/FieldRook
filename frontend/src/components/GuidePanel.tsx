import { useEffect, useState } from "react";
import {
  ApiError,
  cancelRound,
  completePlanStep,
  impossiblePlanStep,
  listProviders,
  sendTurn,
  setHypothesisStatus,
  setTarget,
  switchProvider,
  testLocalProvider,
} from "../api";
import type {
  ClarifyingQuestion,
  DiagnosisTarget,
  Hypothesis,
  InvestigationResponse,
  LocalTestResult,
  ProviderOption,
  TroubleshootStep,
  TurnKind,
} from "../types";
import { EvidenceChip } from "./EvidenceChip";

const STAGE_HELP: Record<string, string> = {
  INTAKE: "Understanding the reported problem.",
  CLARIFYING: "Missing information — your answer decides the next step.",
  PLANNING: "Choosing useful diagnostic steps.",
  INVESTIGATING: "Collecting and interpreting evidence.",
  REASSESSING: "Fresh input received — hypotheses and plan updated.",
  READY_TO_RESOLVE: "Enough evidence for a candidate intervention.",
  VERIFYING: "Testing whether the intervention worked.",
  RESOLVED: "Measured or clearly qualified closure.",
  BLOCKED: "Progress needs information or access FieldRook lacks.",
};

const TARGET_HELP: Record<DiagnosisTarget, string> = {
  local: "This computer — host diagnostics apply.",
  remote: "Another computer — host readings are withheld.",
  unknown: "Not established — confirm which machine is affected.",
};

const KIND_LABELS: Record<TroubleshootStep["kind"], string> = {
  AUTOMATED_READ_ONLY: "Automated check",
  TECHNICIAN_CHECK: "Technician check",
  CLARIFYING_QUESTION: "Question",
  EXTERNAL_SYSTEM_CHECK: "External check",
  PROPOSED_INTERVENTION: "Proposed intervention (guidance only)",
  VERIFICATION: "Verification",
};

const TURN_OPTIONS: { value: TurnKind; label: string }[] = [
  { value: "observation", label: "Observation" },
  { value: "test_result", label: "Test result" },
  { value: "answer", label: "Answer" },
  { value: "correction", label: "Correction" },
  { value: "question", label: "Question for FieldRook" },
];

function statusTone(status: string): string {
  if (status === "confirmed" || status === "done") return "good";
  if (status === "ruled_out" || status === "blocked") return "bad";
  if (status === "weakened" || status === "current") return "warn";
  return "mute";
}

function QuestionCard({
  question,
  invId,
  disabled,
  onUpdate,
  onError,
}: {
  question: ClarifyingQuestion;
  invId: string;
  disabled: boolean;
  onUpdate: (inv: InvestigationResponse) => void;
  onError: (msg: string) => void;
}) {
  const [answer, setAnswer] = useState("");
  const [sending, setSending] = useState(false);
  if (question.status !== "open") {
    return (
      <li className="guide-qa guide-answered">
        <p className="guide-q">{question.question}</p>
        <p className="guide-a">
          <span className="runbook-label">You answered — </span>
          {question.answer}
        </p>
      </li>
    );
  }
  const send = async () => {
    if (!answer.trim() || sending) return;
    setSending(true);
    try {
      const result = await sendTurn(invId, {
        kind: "answer",
        text: answer.trim(),
        questionId: question.question_id,
        shareConsent: false,
      });
      onUpdate(result);
      setAnswer("");
    } catch (e) {
      onError(e instanceof ApiError ? `Answer failed (HTTP ${e.status}): ${e.message}` : String(e));
    } finally {
      setSending(false);
    }
  };
  return (
    <li className="guide-qa guide-open">
      <p className="guide-q">{question.question}</p>
      {question.why && <p className="muted guide-why">Why this matters: {question.why}</p>}
      <div className="guide-answer-row">
        <input
          type="text"
          className="guide-input"
          maxLength={2000}
          placeholder="Type your answer…"
          aria-label={`Answer to: ${question.question}`}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          disabled={disabled || sending}
          onKeyDown={(e) => {
            if (e.key === "Enter") void send();
          }}
        />
        <button
          type="button"
          className="button button-small"
          onClick={() => void send()}
          disabled={disabled || sending || !answer.trim()}
        >
          {sending ? "Sending…" : "Answer"}
        </button>
      </div>
    </li>
  );
}

function StepCard({
  step,
  isCurrent,
  invId,
  disabled,
  onUpdate,
  onError,
  onEvidenceClick,
}: {
  step: TroubleshootStep;
  isCurrent: boolean;
  invId: string;
  disabled: boolean;
  onUpdate: (inv: InvestigationResponse) => void;
  onError: (msg: string) => void;
  onEvidenceClick?: (id: string) => void;
}) {
  const [mode, setMode] = useState<"done" | "blocked" | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const open = step.status === "suggested" || step.status === "current";
  const submit = async () => {
    if (!mode || !text.trim() || sending) return;
    setSending(true);
    try {
      const result =
        mode === "done"
          ? await completePlanStep(invId, step.step_id, text.trim())
          : await impossiblePlanStep(invId, step.step_id, text.trim());
      onUpdate(result);
      setMode(null);
      setText("");
    } catch (e) {
      onError(e instanceof ApiError ? `Step update failed (HTTP ${e.status}): ${e.message}` : String(e));
    } finally {
      setSending(false);
    }
  };
  return (
    <li className={`guide-step guide-step-${step.status}${isCurrent ? " guide-step-current" : ""}`}>
      <div className="guide-step-head">
        <span className={`badge badge-${statusTone(isCurrent ? "current" : step.status)}`}>
          {isCurrent ? "CURRENT" : step.status.toUpperCase()}
        </span>
        <span className="guide-kind">{KIND_LABELS[step.kind]}</span>
        {step.tool_name && <code className="mono muted">{step.tool_name}</code>}
        {step.admin_maybe && <span className="muted">may need admin</span>}
      </div>
      <p className="guide-instruction">{step.instruction}</p>
      {step.why && <p className="muted guide-why">{step.why}</p>}
      {step.expected_observations.length > 0 && (
        <ul className="guide-expected">
          {step.expected_observations.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
      {step.evidence_ids.length > 0 && (
        <div className="guide-refs">
          {step.evidence_ids.map((eid) => (
            <EvidenceChip key={eid} id={eid} onSelect={onEvidenceClick} />
          ))}
        </div>
      )}
      {step.outcome && (
        <p className="guide-outcome">
          <span className="runbook-label">{step.status === "done" ? "Outcome — " : "Why impossible — "}</span>
          {step.outcome}
        </p>
      )}
      {open && mode === null && (
        <div className="guide-step-actions">
          <button
            type="button"
            className="button button-small"
            onClick={() => setMode("done")}
            disabled={disabled}
          >
            Record outcome
          </button>
          <button
            type="button"
            className="button button-ghost button-small"
            onClick={() => setMode("blocked")}
            disabled={disabled}
          >
            Can&apos;t do this
          </button>
        </div>
      )}
      {open && mode !== null && (
        <div className="guide-outcome-row">
          <input
            type="text"
            className="guide-input"
            maxLength={2000}
            placeholder={mode === "done" ? "What did you observe?" : "Why is this step not possible?"}
            aria-label={mode === "done" ? `Outcome for: ${step.instruction}` : `Reason step is impossible: ${step.instruction}`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={disabled || sending}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submit();
              if (e.key === "Escape") {
                setMode(null);
                setText("");
              }
            }}
          />
          <button
            type="button"
            className="button button-small"
            onClick={() => void submit()}
            disabled={disabled || sending || !text.trim()}
          >
            {sending ? "Saving…" : mode === "done" ? "Save outcome" : "Mark impossible"}
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setMode(null);
              setText("");
            }}
            disabled={sending}
          >
            Cancel
          </button>
        </div>
      )}
    </li>
  );
}

function HypothesisCard({
  hypothesis,
  invId,
  disabled,
  onUpdate,
  onError,
  onEvidenceClick,
}: {
  hypothesis: Hypothesis;
  invId: string;
  disabled: boolean;
  onUpdate: (inv: InvestigationResponse) => void;
  onError: (msg: string) => void;
  onEvidenceClick?: (id: string) => void;
}) {
  const [judging, setJudging] = useState(false);
  const [status, setStatus] = useState("ruled_out");
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);
  const submit = async () => {
    if (!reason.trim() || sending) return;
    setSending(true);
    try {
      const result = await setHypothesisStatus(invId, hypothesis.hypothesis_id, status, reason.trim());
      onUpdate(result);
      setJudging(false);
      setReason("");
    } catch (e) {
      onError(e instanceof ApiError ? `Judgment failed (HTTP ${e.status}): ${e.message}` : String(e));
    } finally {
      setSending(false);
    }
  };
  return (
    <li className="guide-hyp">
      <div className="guide-step-head">
        <span className={`badge badge-${statusTone(hypothesis.status)}`}>
          {hypothesis.status.replace("_", " ").toUpperCase()}
        </span>
        <strong>{hypothesis.title}</strong>
      </div>
      {hypothesis.description && <p className="muted">{hypothesis.description}</p>}
      {(hypothesis.supporting_evidence_ids.length > 0 ||
        hypothesis.contradicting_evidence_ids.length > 0) && (
        <div className="guide-refs">
          {hypothesis.supporting_evidence_ids.map((eid) => (
            <EvidenceChip key={`s-${eid}`} id={eid} onSelect={onEvidenceClick} />
          ))}
          {hypothesis.contradicting_evidence_ids.map((eid) => (
            <span key={`c-${eid}`} className="guide-contra">
              <EvidenceChip id={eid} onSelect={onEvidenceClick} />
            </span>
          ))}
        </div>
      )}
      {hypothesis.history.length > 1 && (
        <details className="guide-history">
          <summary>History ({hypothesis.history.length})</summary>
          <ul>
            {hypothesis.history.map((event, i) => (
              <li key={i}>
                <span className="muted">round {event.round} · {event.status}</span> — {event.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
      {!judging ? (
        <button
          type="button"
          className="link-button"
          onClick={() => setJudging(true)}
          disabled={disabled}
        >
          Record your judgment
        </button>
      ) : (
        <div className="guide-judge-row">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            disabled={disabled || sending}
            aria-label={`Judgment for: ${hypothesis.title}`}
          >
            <option value="ruled_out">Rule out</option>
            <option value="weakened">Weaken</option>
            <option value="confirmed">Confirm</option>
            <option value="active">Reopen</option>
          </select>
          <input
            type="text"
            className="guide-input"
            maxLength={1000}
            placeholder="Why? (recorded in history)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={disabled || sending}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submit();
              if (e.key === "Escape") setJudging(false);
            }}
          />
          <button
            type="button"
            className="button button-small"
            onClick={() => void submit()}
            disabled={disabled || sending || !reason.trim()}
          >
            {sending ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </li>
  );
}

function ProviderDetail({
  option,
  providerName,
  localTest,
  testingLocal,
  disabled,
  onTest,
}: {
  option: ProviderOption | null;
  providerName: string;
  localTest: LocalTestResult | null;
  testingLocal: boolean;
  disabled: boolean;
  onTest: () => void;
}) {
  if (providerName !== "local" && !option) return null;
  const profile = option?.profile ?? localTest?.profile ?? null;
  return (
    <div className="guide-provider">
      {option && (
        <p className="muted">
          <span className="runbook-label">{option.model} — </span>
          {option.available ? option.reason : `unavailable: ${option.reason}`} · vision{" "}
          {option.vision ? "yes" : "no"} · tool calling {option.tool_calling ? "yes" : "no"}
        </p>
      )}
      {providerName === "local" && profile && (
        <details className="guide-history">
          <summary>
            Local model profile{option?.api_style ? ` · ${option.api_style}` : ""}
            {profile.perf_class ? ` · ${profile.perf_class}` : ""}
          </summary>
          <p className="muted">{profile.notes}</p>
          <p className="muted">
            context {profile.context_window.toLocaleString()} tokens
            {profile.storage_gb ? ` · ${profile.storage_gb} GB on disk` : ""}
            {profile.thinking ? " · extended thinking" : " · direct answers"}
            {` · source: ${profile.source}`}
          </p>
          {profile.install_hint && (
            <p className="muted">
              <code className="mono">{profile.install_hint}</code>
            </p>
          )}
        </details>
      )}
      {providerName === "local" && (
        <div className="guide-test-row">
          <button
            type="button"
            className="button button-small"
            onClick={onTest}
            disabled={disabled || testingLocal}
          >
            {testingLocal ? "Testing…" : "Test local connection"}
          </button>
          {localTest && (
            <span role="status" data-testid="local-test-result" className="muted">
              {localTest.ok
                ? `Reachable via ${localTest.api_style ?? "?"} · ${localTest.latency_s ?? "?"}s · reply ${
                    localTest.reply_ok ? "OK" : JSON.stringify(localTest.reply ?? "")
                  }`
                : `Not reachable: ${localTest.error ?? "unknown error"}`}
            </span>
          )}
        </div>
      )}
      {providerName === "local" && localTest?.vision_warning && (
        <p className="warn">{localTest.vision_warning}</p>
      )}
      {providerName === "local" && (localTest?.server_caps?.length ?? 0) > 0 && (
        <p className="muted">
          Server advertises: <code className="mono">{localTest?.server_caps?.join(", ")}</code>
        </p>
      )}
    </div>
  );
}

export function GuidePanel({
  investigation,
  onUpdate,
  onEvidenceClick,
  onError,
}: {
  investigation: InvestigationResponse;
  onUpdate: (inv: InvestigationResponse) => void;
  onEvidenceClick?: (id: string) => void;
  onError: (msg: string) => void;
}) {
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [turnKind, setTurnKind] = useState<TurnKind>("observation");
  const [turnText, setTurnText] = useState("");
  const [turnFile, setTurnFile] = useState<File | null>(null);
  const [turnConsent, setTurnConsent] = useState(false);
  const [confirmCloud, setConfirmCloud] = useState(false);
  const [working, setWorking] = useState<string | null>(null);
  const [localTest, setLocalTest] = useState<LocalTestResult | null>(null);
  const [testingLocal, setTestingLocal] = useState(false);
  const [turnElapsed, setTurnElapsed] = useState(0);
  const [cancelState, setCancelState] = useState<"idle" | "sending" | "requested">("idle");

  useEffect(() => {
    let cancelled = false;
    listProviders().then(
      (options) => {
        if (!cancelled) setProviders(options);
      },
      () => {
        /* provider list is advisory; the investigation works without it */
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const invId = investigation.investigation_id;
  const openQuestions = investigation.questions.filter((q) => q.status === "open");
  const answeredQuestions = investigation.questions.filter((q) => q.status !== "open");
  const currentStep =
    investigation.plan?.steps.find((s) => s.step_id === investigation.plan?.current_step_id) ??
    null;
  const otherSteps = (investigation.plan?.steps ?? []).filter(
    (s) => s.step_id !== investigation.plan?.current_step_id,
  );
  const budgetLeft = investigation.tool_calls_max - investigation.tool_calls_used;
  const providerName = investigation.provider_info?.name ?? "simulated";
  const sensitive = investigation.has_screenshot || investigation.evidence.length > 0 || investigation.notes.length > 0;

  useEffect(() => {
    setLocalTest(null);
  }, [providerName]);

  useEffect(() => {
    if (working !== "turn") {
      setTurnElapsed(0);
      setCancelState("idle");
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(
      () => setTurnElapsed((Date.now() - started) / 1000),
      500,
    );
    return () => window.clearInterval(timer);
  }, [working]);

  const fail = (what: string) => (e: unknown) => {
    onError(e instanceof ApiError ? `${what} failed (HTTP ${e.status}): ${e.message}` : String(e));
  };

  const changeTarget = async (target: DiagnosisTarget) => {
    if (target === investigation.target || working) return;
    setWorking("target");
    try {
      onUpdate(await setTarget(invId, target));
    } catch (e) {
      fail("Target change")(e);
    } finally {
      setWorking(null);
    }
  };

  const changeProvider = async (name: string) => {
    if (name === providerName || working) return;
    if (name === "meta" && sensitive && !confirmCloud) {
      onError("Switching to the Meta cloud would transmit this investigation. Tick the authorization box first.");
      return;
    }
    setWorking("provider");
    try {
      onUpdate(await switchProvider(invId, name, name === "meta" && confirmCloud));
      setConfirmCloud(false);
    } catch (e) {
      fail("Provider switch")(e);
    } finally {
      setWorking(null);
    }
  };

  const runLocalTest = async () => {
    if (testingLocal || working) return;
    setTestingLocal(true);
    try {
      setLocalTest(await testLocalProvider());
    } catch (e) {
      setLocalTest({
        ok: false,
        model: "",
        error: e instanceof ApiError ? `HTTP ${e.status}: ${e.message}` : String(e),
      });
    } finally {
      setTestingLocal(false);
    }
  };

  const cancelTurn = async () => {
    if (cancelState !== "idle" || working !== "turn") return;
    setCancelState("sending");
    try {
      onUpdate(await cancelRound(invId));
      setCancelState("requested");
    } catch (e) {
      setCancelState("idle");
      fail("Cancel")(e);
    }
  };

  const send = async () => {
    if (!turnText.trim() || working) return;
    if (turnFile && !turnConsent) {
      onError("Sharing consent is required to send the screenshot — check the consent box or remove the image.");
      return;
    }
    setWorking("turn");
    try {
      const result = await sendTurn(invId, {
        kind: turnKind,
        text: turnText.trim(),
        shareConsent: turnConsent,
        screenshot: turnFile,
      });
      onUpdate(result);
      setTurnText("");
      setTurnFile(null);
      setTurnConsent(false);
    } catch (e) {
      fail("Turn")(e);
    } finally {
      setWorking(null);
    }
  };

  return (
    <div className="guide">
      <section className="card guide-status">
        <div className="card-head">
          <h2>Guided investigation</h2>
          <span className={`badge badge-${statusTone(investigation.stage === "RESOLVED" ? "confirmed" : investigation.stage === "BLOCKED" ? "blocked" : investigation.stage === "CLARIFYING" ? "current" : "mute")}`}>
            {investigation.stage.replace(/_/g, " ")}
          </span>
        </div>
        <p className="muted">{STAGE_HELP[investigation.stage] ?? ""}</p>
        {investigation.warnings.map((w, i) => (
          <p key={i} className="warn">
            {w}
          </p>
        ))}
        <div className="guide-meta-grid">
          <label className="field">
            <span>Diagnostic target</span>
            <select
              value={investigation.target}
              onChange={(e) => void changeTarget(e.target.value as DiagnosisTarget)}
              disabled={working !== null}
              aria-label="Diagnostic target"
            >
              <option value="local">This computer</option>
              <option value="remote">Another computer</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label className="field">
            <span>Inference provider</span>
            <select
              value={providerName}
              onChange={(e) => void changeProvider(e.target.value)}
              disabled={working !== null}
              aria-label="Inference provider"
            >
              {(providers.length > 0
                ? providers
                : [
                    { name: "meta", reason: "" },
                    { name: "simulated", reason: "" },
                    { name: "local", reason: "" },
                  ]
              ).map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                  {"available" in p && !p.available ? " (unavailable)" : ""}
                </option>
              ))}
              <option value="auto">auto (server default)</option>
            </select>
          </label>
          <p className="muted guide-budget">
            Round {investigation.rounds_used} · {budgetLeft} of {investigation.tool_calls_max} tool
            calls left
            {investigation.provider_info && (
              <>
                {" "}· {investigation.provider_info.model || investigation.provider_info.name} ·{" "}
                {investigation.provider_info.processing_location === "cloud"
                  ? "processed in the Meta cloud"
                  : investigation.provider_info.processing_location === "local"
                    ? "processed on this computer"
                    : "no cloud processing"}
              </>
            )}
          </p>
        </div>
        <ProviderDetail
          option={providers.find((p) => p.name === providerName) ?? null}
          providerName={providerName}
          localTest={localTest}
          testingLocal={testingLocal}
          disabled={working !== null}
          onTest={() => void runLocalTest()}
        />
        <p className="muted">{TARGET_HELP[investigation.target]}</p>
        {providerName !== "meta" && sensitive && (
          <label className="check guide-confirm">
            <input
              type="checkbox"
              checked={confirmCloud}
              onChange={(e) => setConfirmCloud(e.target.checked)}
            />
            <span>
              I authorize transmitting this investigation&apos;s screenshots, evidence, and notes to
              the Meta cloud if I switch providers.
            </span>
          </label>
        )}
      </section>

      {investigation.blocked_reason && (
        <section className="card guide-blocked" role="alert">
          <h2>Blocked</h2>
          <p>{investigation.blocked_reason}</p>
          <p className="muted">
            Answer a question, report an observation, or switch the diagnostic target to reopen
            the investigation.
          </p>
        </section>
      )}

      {(investigation.understanding || investigation.assistant_message) && (
        <section className="card">
          <div className="card-head">
            <h2>Current understanding</h2>
          </div>
          {investigation.understanding && <p>{investigation.understanding}</p>}
          {investigation.assistant_message && (
            <p className="guide-assistant">{investigation.assistant_message}</p>
          )}
        </section>
      )}

      {openQuestions.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Questions for you</h2>
            <span className="muted">{openQuestions.length} open</span>
          </div>
          <ul className="guide-list">
            {openQuestions.map((q) => (
              <QuestionCard
                key={q.question_id}
                question={q}
                invId={invId}
                disabled={working !== null}
                onUpdate={onUpdate}
                onError={onError}
              />
            ))}
          </ul>
        </section>
      )}

      {currentStep && (
        <section className="card guide-current">
          <div className="card-head">
            <h2>Recommended next step</h2>
            <span className="muted">{KIND_LABELS[currentStep.kind]}</span>
          </div>
          <ul className="guide-list">
            <StepCard
              step={currentStep}
              isCurrent
              invId={invId}
              disabled={working !== null}
              onUpdate={onUpdate}
              onError={onError}
              onEvidenceClick={onEvidenceClick}
            />
          </ul>
        </section>
      )}

      {otherSteps.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Full plan</h2>
            <span className="muted">
              {otherSteps.filter((s) => s.status === "done").length} done ·{" "}
              {otherSteps.filter((s) => s.status === "suggested" || s.status === "current").length}{" "}
              upcoming
            </span>
          </div>
          <ul className="guide-list">
            {otherSteps.map((step) => (
              <StepCard
                key={step.step_id}
                step={step}
                isCurrent={false}
                invId={invId}
                disabled={working !== null}
                onUpdate={onUpdate}
                onError={onError}
                onEvidenceClick={onEvidenceClick}
              />
            ))}
          </ul>
        </section>
      )}

      {investigation.hypotheses.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Hypotheses</h2>
            <span className="muted">evidence-linked · history preserved</span>
          </div>
          <ul className="guide-list">
            {investigation.hypotheses.map((hyp) => (
              <HypothesisCard
                key={hyp.hypothesis_id}
                hypothesis={hyp}
                invId={invId}
                disabled={working !== null}
                onUpdate={onUpdate}
                onError={onError}
                onEvidenceClick={onEvidenceClick}
              />
            ))}
          </ul>
        </section>
      )}

      {answeredQuestions.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Answered</h2>
            <span className="muted">{answeredQuestions.length}</span>
          </div>
          <ul className="guide-list">
            {answeredQuestions.map((q) => (
              <QuestionCard
                key={q.question_id}
                question={q}
                invId={invId}
                disabled={working !== null}
                onUpdate={onUpdate}
                onError={onError}
              />
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Talk to FieldRook</h2>
          <span className="muted">continues this investigation</span>
        </div>
        <div className="guide-turn-row">
          <label className="field">
            <span>This is…</span>
            <select
              value={turnKind}
              onChange={(e) => setTurnKind(e.target.value as TurnKind)}
              disabled={working !== null}
              aria-label="Turn kind"
            >
              {TURN_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          <span>What did you see, try, or want to ask?</span>
          <textarea
            id="turn-input"
            className="problem"
            rows={3}
            maxLength={2000}
            placeholder="Excel opens local files fine — only files from Teams fail with 0x80070005."
            value={turnText}
            onChange={(e) => setTurnText(e.target.value)}
            disabled={working !== null}
          />
        </label>
        <div className="file-row">
          <label className="field">
            <span>Follow-up screenshot (optional)</span>
            <input
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => setTurnFile(e.currentTarget.files?.[0] ?? null)}
              disabled={working !== null}
            />
          </label>
          {turnFile && (
            <label className="check">
              <input
                type="checkbox"
                checked={turnConsent}
                onChange={(e) => setTurnConsent(e.target.checked)}
                disabled={working !== null}
              />
              <span>I am authorized to share this screenshot for analysis.</span>
            </label>
          )}
        </div>
        <div className="controls">
          <button
            type="button"
            className="button"
            onClick={() => void send()}
            disabled={working !== null || !turnText.trim()}
          >
            {working === "turn" ? "Sending…" : "Send to FieldRook"}
          </button>
          {working === "turn" && (
            <span className="muted" role="status">
              Working — elapsed {turnElapsed.toFixed(0)}s. The page updates when the round
              completes.
            </span>
          )}
          {working === "turn" && (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => void cancelTurn()}
              disabled={cancelState !== "idle"}
            >
              {cancelState === "idle"
                ? "Cancel this round"
                : cancelState === "sending"
                  ? "Cancelling…"
                  : "Cancellation requested"}
            </button>
          )}
          {working === "turn" && cancelState === "requested" && (
            <span className="muted">
              The current model call finishes, then the round stops. Evidence is kept.
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
