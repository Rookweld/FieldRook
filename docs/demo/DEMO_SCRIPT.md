# FieldRook — 3-Minute Demo Script

Total: 3:00. Every step below maps to real application behavior; nothing is
staged or faked. Bracketed text is narration; bullets are on-screen actions.

## Setup (before recording)

1. `scripts/demo/preflight.ps1` — all checks green.
2. Backend on `127.0.0.1:8000` with `MODEL_API_KEY` set (LIVE MODEL badge).
3. Frontend on `localhost:5173`.
4. `scripts/demo/reset-demo.ps1` — worker healthy.
5. `scripts/demo/inject-failure.ps1` — worker failed (Scenario B armed).

## 00:00-00:20 — The problem

> "IT technicians drown in fragmented tools: event viewers, service consoles,
> task schedulers, and chatbots that guess. FieldRook is different — it
> investigates like a technician and proves what it claims."

- Show the workstation: FieldRook header, Investigate / Understand / Resolve
  stages, empty incident workspace.
- Point at the OBSERVED / INFERRED / UNVERIFIED legend: "Belief is never
  presented as measurement."

## 00:20-01:05 — The investigation (Scenario B)

> "Our background worker just failed. I describe the symptom in plain words —
> no service picker, no query language."

- Type: "The FieldRook demo worker appears to be down. Investigate its health."
- Click Investigate. Watch the Diagnostic activity timeline fill with REAL
  records: model reasoning, `get_demo_worker_health` requested, evidence
  `ev-1` collected, investigation complete.
- Open the evidence card: live heartbeat JSON (status failed, verified PID).
- "Muse Spark chose the diagnostic tool. FieldRook executed a predefined,
  read-only check and kept the receipt."

## 01:05-01:40 — The intelligence

> "Now the assessment. Facts carry evidence chips — click one and it jumps to
> the underlying observation. Hypotheses are labeled INFERRED. Gaps are
> labeled UNVERIFIED, not papered over."

- Scroll the Diagnosis panel: observed facts with `ev-1` chips, hypotheses,
  missing evidence, next steps.
- Click an evidence chip to show navigation to the evidence card.
- Show the resolution banner: "UNRESOLVED — diagnosed, no verified correction."
- "This is why FieldRook is more than a chatbot: every claim is traceable,
  and uncertainty is a first-class output."

## 01:40-02:35 — The controlled fix

> "FieldRook proposes a recovery — but the AI cannot execute it. Only I can,
> and only this exact action on this exact target."

- Stage 3 — Action Center: proposal card (action, target, reason, evidence,
  expected result, risk, verification method).
- Emphasize: nothing changed so far — show worker still failed
  (`scripts/demo/check-health.ps1` in a terminal, or the evidence).
- Click "Approve action": the proposal turns APPROVED and still nothing has
  executed. Then click "Execute approved action" as the separate deliberate
  step. Watch real transitions: APPROVED → EXECUTING → independent
  verification → **VERIFIED_RESOLVED**.
- Show before/after: `failed → healthy`, verified by a fresh diagnostic read,
  not by model confidence.
- "Rejection would have left the system untouched. Approval was single-use
  and bound to these exact arguments."

## 02:35-03:00 — The impact

> "The incident is reviewable forever: full timeline, evidence, the human
> decision, the execution record, and the verified outcome — exportable as a
> ticket-ready report."

- Open History: the incident row with `VERIFIED_RESOLVED`.
- Download the Markdown report; flash sections 1-11.
- Close: "FieldRook turns hours of fragmented troubleshooting into one
  evidence-backed workflow: Diagnose. Verify. Resolve."

## If time allows (overflow, not in the 3 minutes)

- Scenario A: force fixtures, investigate "PowerShell windows flash every few
  minutes" — show the phantom task evidence and the misplaced `-WindowStyle
  Hidden` finding labeled suspicious-but-unverified.
- Scenario C: "My laptop freezes randomly" — show bounded evidence and an
  honest UNRESOLVED outcome with recommended next diagnostics.
- Reject path: propose recovery on a failed worker, click Reject, show the
  worker still failed with zero executions.
