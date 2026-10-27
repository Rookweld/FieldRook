# FieldRook — Technical Highlights

What is genuinely hard or interesting under the hood, for a technical jury.

## 1. Evidence-typed reasoning (not a chatbot)

Every model claim is classified OBSERVED (measured), INFERRED (hypothesis),
or UNVERIFIED (unknown). Factual claims must cite collected evidence IDs;
the backend validates citations and repairs or flags uncited claims. The UI
renders evidence chips that navigate to the underlying records.

## 2. Strict tool-calling loop on Muse Spark 1.3

The model requests named tools with schema-validated arguments; the backend
executes predefined implementations (services, processes, event logs,
application crashes, OS, network, scheduled tasks, demo-worker health,
error codes — see `docs/TOOLS.md`). Everything is read-only except one
explicitly labeled active DNS test. No arbitrary PowerShell exists anywhere
in the path. Budgets (8 + 4 calls), per-tool timeouts, truncation,
same-round duplicate suppression, cross-round re-check comparison against
preserved history, early stopping on unproductive rounds, contradiction
detection between observations, and malformed-call rejection are enforced
server-side. Every tool call answers with a matching tool message
(protocol-correct even on budget cutoff).

## 3. Human-gated corrective actions

Muse Spark may PROPOSE a registered action; it can never execute one.
Approval is an explicit local API call producing a single-use token (5-minute
TTL) bound to exact arguments and invalidated if the investigation changes.
Execution is single-flight with timeout, fenced to the application-owned
demo worker (live PID/command-line verification), and followed by
INDEPENDENT verification diagnostics. The model cannot override
VERIFIED_UNRESOLVED. Rejection is zero-execution, proven by tests.

## 4. Deterministic verification states

PROPOSED → AWAITING_APPROVAL → APPROVED → EXECUTING → EXECUTED_UNVERIFIED →
VERIFIED_RESOLVED / VERIFIED_UNRESOLVED / EXECUTION_FAILED /
VERIFICATION_FAILED. Outcomes derive from fresh diagnostic reads (e.g. live
heartbeat status), never from exit codes or model confidence. Backend
restarts fail stuck executions closed and preserve the full audit trail in
SQLite (screenshots and raw tokens never persisted).

## 5. Honest uncertainty as a feature

Scenario C ("laptop freezes randomly") collects bounded evidence and reports
UNRESOLVED with missing-evidence lists and next diagnostics — no invented
root cause, no unsupported action. Fixture mode is always labeled; simulated
output is never presented as a live model call.

## 6. Division of labor (important)

- Meta Muse Spark: symptom understanding, diagnostic planning, tool
  selection, hypothesis generation, screenshot vision.
- FieldRook: evidence collection, citation validation, safety policy,
  approval enforcement, fenced execution, independent verification,
  persistence, export.

The model advises; FieldRook measures, gates, and verifies.

## 7. Resolution as measurement (M008)

A resolution plan is a contract: supporting evidence, an intended state, and
criteria that name a tool, a value path, and a comparison. Confirm Fix
captures a pre-fix baseline, waits for a recorded intervention (a linked
authorized execution or an explicitly-labeled manual claim), re-runs the
criterion diagnostics, and grades fresh readings into VERIFIED_RESOLVED,
NOT_RESOLVED, or INCONCLUSIVE. Verification is read-only and budget-bound;
it cannot authorize or execute anything, and a manual "done" is stored as a
claim, never as proof.

## 8. Memory without mysticism (M009)

Resolved incidents persist as redacted fingerprints — symptom tokens, a
keyword category, service/app identity, event codes, and salient evidence
values. Matching is arithmetic over inspectable signals (identity +4, shared
event code +3, evidence value +3, category +2, symptom +1): every suggestion
shows why it matched and where the evidence differs, and a bare category
overlap never surfaces. Inferred causes stay labeled as hypotheses; only a
technician-attested cause counts as confirmed. Rechecks re-run stored
criteria on demand and report CONFIRMED, REGRESSION, or INCONCLUSIVE —
nothing monitors in the background, and the library never leaves localhost
except as a short technician-initiated hypothesis prompt.

## 9. Pilot-hardened honesty (M011)

The technician pilot ran the product against genuine Windows data and
fixed what broke: bare-hex error codes as Windows spells them
(`80073d02`, no `0x`) now decode instead of failing; truncation and
fixture-fallback warnings render on the evidence card instead of hiding
in the JSON; timeline durations render once. The ambiguous-symptom
trial is the honest-uncertainty story told with real data: six live
tool calls, two truncated readings, and a low-confidence "undetermined"
whose missing-evidence list names the truncation as the blocker. Live
latency measured 11–42s per investigation with zero bad citations
(see `docs/pilot/M011_PILOT.md`).
