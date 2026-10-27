# M011 Technician Pilot — live validation report (2026-10-27)

Pilot stack: backend `http://127.0.0.1:8123` (`FIELDROOK_FIXTURES=never`,
real `MODEL_API_KEY`, isolated DB `m11-pilot.db`, isolated demo state
`m11-demo`), frontend `http://localhost:5174`. The operator's own stack
(`:8000` + demo worker) was never touched. No real services, tasks,
network settings, or applications were modified; the only executed
change was the fenced demo-worker recovery against the isolated pilot
worker state.

## Genuine Windows findings (live model + live diagnostics)

All evidence below carries `:live` sources; every investigation shows
`LIVE DIAGNOSTICS` + `LIVE MODEL` badges in the UI.

| ID | Problem | Latency | Tools (calls) | Result |
| -- | ------- | ------- | ------------- | ------ |
| L1 apps | Excel crashed in the last day? | 27.9s | app crashes, process info (2) | Honest negative: no Excel crash; 0 bad citations |
| L2 service | wuauserv healthy? | 18.4s | service details, process info (2) | Correct: Stopped/Manual on-demand idle, no process; 0 bad citations |
| L3 network | DNS resolving? | 21.7s | dns config, dns test (2) | Functional, from measurement; 0 bad citations |
| L4 task | Phantom task safe to disable? | 21.2s | scheduled tasks (1) | Honest absence: task does not exist; 0 bad citations |
| L5 ambiguous | Slow this morning, what happened? | 41.8s | os info, event logs ×2, tasks ×2, crashes (6) | Honest low-confidence "undetermined" + 4 explicit uncertainties naming truncation as the blocker |
| UI fresh | Anything crashed today? | n/a (walk) | crashes, os info, event logs, error codes (7) | "No classic application crash today"; 1 failed collection (bare hex — the M011 defect below) |
| UI follow-up | Which app crashed most? | n/a (walk) | round 2 | Continued the same investigation cleanly |
| Repeat | Crashed today? (again) | 26.3s | — | Matched the recorded entry, strength 9, signals + differences shown; bare-hex code decoded after the fix |
| Worker | Demo worker running? | 11.3s | demo-worker health | unknown → propose → approve → execute → VERIFIED_RESOLVED (pilot worker PID 55396, stopped at cleanup) |

Live-data cross-checks: persistence survived a backend restart (6
evidence / 22 activity intact); knowledge recorded a live incident and
matched its repeat with event-code + symptom + category signals and
honest differences; markdown export of L2 carries live markers
(6133 chars). Two evidence items arrived truncated (12000-char cap)
with `_truncated` flags; principals redacted (`<user>`) as designed.

Model usage: 8 live investigations + 1 follow-up + 10 capped gauntlet
cases. Per-call token counts and costs are not exposed by the provider
responses (same limitation as ever); latency and call counts are
recorded instead. Biggest live run: 41.8s / 6 calls (L5).

## Simulated results (for contrast, not evidence)

- Backend pytest: **252 passed** (251 M010 + 1 M011 hex regression test).
- Gauntlet: **47/47** (37 fixture/tool + 10 capped live-model reasoning
  over fixture diagnostics); raw JSON
  `backend/eval/results/20261027T125857Z.json` (gitignored).
- Frontend build clean; Playwright e2e **17/17** (fixtures, no key).
- Gitleaks: staged changes clean; tree scan shows only the ignored
  `.env` and the documented harmless demo hash.

## Defects found live and fixed

1. **Bare-hex error codes rejected** (`errorcodes.py`): the tool
   advertises "hex" but `int(text, 0)` rejects `80073d02` as spelled in
   Windows logs. Fix: fall back to base-16 when base-0 fails
   (all-digit input still reads decimal first); tool description now
   says the `0x` prefix is optional. Regression test
   `test_bare_hex_spelling_decodes_like_prefixed`; verified on the
   repeat investigation (`0x80073D02`, no error).
2. **Evidence warnings buried** (`EvidenceCards.tsx`): truncation and
   fixture-fallback warnings lived inside the JSON blob only. Cards now
   render `data.warnings` above the preview. Verified in the live UI
   walk ("was truncated" asserted + screenshotted).
3. **Duration shown twice** (`Timeline.tsx`): titles ending in "Nms" got
   a redundant "(Nms)" suffix. The suffix now skips when the title
   already carries the duration.
4. **Stale footer** (`App.tsx`): still read "Milestone 009"; bumped to
   011. No test depended on it.

## Operator-facing deliverables

- `docs/FIRST_RUN.md` — ten-minute first-run guide.
- `docs/ACCEPTANCE.md` — manual acceptance checklist with pass criteria.
- `docs/assets/fieldrook-m011-*.png` — live landing, service lookup,
  live investigation, truncation warnings.
- `HACKATHON.md` — M010 hash `d29b41a` recorded in the table; M011 prose
  added (table row follows in the docs commit, per convention).

## What remains / M012 candidates

- Truncation is now visible but still lossy: a "narrow the query"
  affordance (tighter filters re-run, not a bigger cap) would close
  the loop the L5 uncertainties point at.
- Gauntlet exit-code flicker on all-pass Windows runs (noted in M010)
  did not reproduce this round (exit 0).
- Live-machine rehearsal with fixtures off is now done (this pilot);
  the next validation step is a second human technician working the
  acceptance checklist on their own machine.
