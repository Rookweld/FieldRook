# FieldRook — Technical Highlights

What is genuinely hard or interesting under the hood, for a technical jury.

## 1. Evidence-typed reasoning (not a chatbot)

Every model claim is classified OBSERVED (measured), INFERRED (hypothesis),
or UNVERIFIED (unknown). Factual claims must cite collected evidence IDs;
the backend validates citations and repairs or flags uncited claims. The UI
renders evidence chips that navigate to the underlying records.

## 2. Strict tool-calling loop on Muse Spark 1.3

The model requests named tools with schema-validated arguments; the backend
executes predefined read-only implementations (services, event logs, OS,
network, scheduled tasks, demo-worker health, error codes). No arbitrary
PowerShell exists anywhere in the path. Budgets (8 + 4 calls), per-tool
timeouts, truncation, and malformed-call rejection are enforced server-side.
Every tool call answers with a matching tool message (protocol-correct even
on budget cutoff).

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
