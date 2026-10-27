# FieldRook — Judging Notes (Meta Hackathon 2026)

How FieldRook maps to the official criteria. Weights: Impact 30%, Use of
Meta AI Tooling 25%, Technical Depth & Execution 20%, Demo 25%.

## Impact (30%)

IT troubleshooting is fragmented across consoles, logs, and guesswork, and
wrong fixes cost downtime. FieldRook compresses the loop — symptoms in,
evidence out, verified resolution documented — into one workstation usable
by working technicians. The exportable incident report (11 sections: summary
to verified outcome) drops directly into existing ticket workflows. Built
for the "Build for Your World" theme from a REAL troubleshooting case (the
phantom PowerShell scheduled task the author actually experienced).

## Use of Meta AI Tooling (25%)

Muse Spark 1.3 (`muse-spark-1.3` via the Meta Model API) drives:
natural-language symptom understanding, diagnostic planning, multi-step
tool selection across 11 read-only tools, screenshot/vision interpretation
of Windows error dialogs, evidence-cited assessment generation, and
follow-up reasoning with context reuse. The demo proves live integration
(LIVE MODEL badge, real tool-call timeline) with an explicitly labeled
simulated fallback — never misrepresented.

## Technical Depth & Execution (20%)

New during the hackathon (Oct 26 - Nov 4, 2026; see HACKATHON.md commits):
FastAPI backend with strict tool registry, protocol-correct agentic loop
with citation validation/repair, corrective-action subsystem (registry,
policy, single-use approval, fenced executor, independent verifier, audit),
SQLite persistence with migrations, Markdown/JSON export, deterministic
Win32/HRESULT decoder, local-origin CSRF protections, application-owned
demo worker with heartbeat verification, and a React/TypeScript workstation
(OBSERVED/INFERRED/UNVERIFIED design, timeline, evidence cards, Action
Center, history). 130+ automated backend tests; production frontend build;
GitHub Actions validation. Pre-existing work: none — the repository was
created during the event. Third-party packages and the Apache-2.0 text are
the only external artifacts.

## Demo (25%)

Three reproducible scenarios, all runnable from scripts/demo/ without admin
rights: (A) phantom PowerShell task diagnosis from fixtures with honest
suspicion labeling; (B) full live loop — fail, investigate, approve,
execute, VERIFIED_RESOLVED with before/after proof; (C) insufficient
evidence with calibrated UNRESOLVED honesty. DEMO_SCRIPT.md paces the
3-minute video; DEMO_CHECKLIST.md de-risks demo day including live-API
failure fallbacks.

## Bonus: Best Agentic Use-Case

FieldRook shows meaningful multi-step autonomy — the model plans, calls
tools, adapts to results, and proposes fixes across investigation rounds —
while safety stays architectural, not prompt-based: allowlisted actions,
exact-match single-use approvals, fenced execution, and verification the
model cannot override. Autonomy where it helps, control where it matters.
