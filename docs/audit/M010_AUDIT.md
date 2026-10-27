# M010 Product Audit — reproducible findings (2026-10-27)

Audit stack: backend `http://127.0.0.1:8123` (fixtures=always, isolated DB),
frontend `http://localhost:5174`. Playwright walk `audit-walk.js` covered
landing, history/library empty states, DNS/network/phantom/crash/worker
investigations, evidence navigation, follow-up, contradictions, resolution
flow, notes + knowledge save + history reopen, service lookup, empty submit,
and a 390px viewport. Zero console errors, zero page errors, zero failed
requests across the walk. Screenshots: `.fieldrook-tmp/audit/` (working
copies; before/after pairs in `docs/assets/` at delivery).

Field trials T1–T5 (simulated + fixtures): 0.05–0.07s per investigation,
0 bad citations everywhere, correct tool triage except T4.

## Findings (numbered for the report)

1. **[triage] "task" problems miss scheduled-tasks diagnostics.**
   Repro: "Is the FieldRookDemoPhantom task safe to disable?" collects
   os_info + service_list + event_logs — never `get_scheduled_tasks`.
   `SCHEDULED_KEYWORDS` needs "scheduled task" verbatim; a bare "task"
   falls through to the generic plan. (Trial T4.)
2. **[label] Resolution label ignores plans.**
   Repro: complete an M008 flow to VERIFIED_RESOLVED — the header still
   reads "UNRESOLVED — diagnosed, no verified correction".
   `resolutionOf()` only inspects executions/proposals.
3. **[nav] Stage stepper ignores plans.**
   Repro: same as (2) — the stepper stays on "2 Understand".
   `stageOf()` only inspects proposals/executions.
4. **[stale] Assessment goes stale after plan runs.**
   Repro: baseline + verify add evidence, but Diagnosis still says
   "1 of 1 evidence items usable" with 3 items present. Reverify rebuilds
   the simulated assessment (M007); baseline/verify do not (M008 gap).
5. **[clutter] Historical evidence dumps full JSON inline.**
   Repro: any re-check produces stacked near-identical JSON cards.
   Superseded items should collapse to a summary line (details still
   expandable).
6. **[nav] No in-page stage navigation.**
   Repro: a resolved investigation page is 4000px+; follow-up sits at the
   bottom; the stepper is not clickable. Steps should scroll to sections.
7. **[timeline] Plan runs lump into Round 1.**
   Repro: "19 records · 1 round" after baseline + verify. Round grouping
   only splits follow-ups and reverifies, not plan baselines/verifications.
8. **[label] Header badges ambiguous.**
   Repro: SIMULATED MODEL + LIVE DIAGNOSTICS side by side reads as a
   contradiction. The second badge is host *capability*, not active mode.
   Tooltips + clearer active-mode affordance needed.
9. **[perf] Library search hits the API per keystroke.**
   Repro: type in Knowledge search — one `GET /api/knowledge` per char.
   Debounce.
10. **[a11y] No visible focus styles.**
    Repro: tab through the workstation — only browser-default focus rings,
    inconsistent with the theme. Add `:focus-visible` treatment.

## Checked and cleared (no change)

- Empty problem submit is correctly disabled; history/library empty states
  are helpful; mobile 390px stacks without overflow or clipping.
- `MODEL_API_KEY is not set` warning is accurate honesty signaling.
- Runbook step 1 ("Re-run with live diagnostics") is simulated-mode-only
  text; live investigations get model-authored steps. Not a bug.
- Overview lead-title duplication with Diagnosis is an accepted summary
  pattern (e2e scopes assertions); not worth churning.
- Investigation latency 0.05–0.07s simulated; no slow renders observed;
  no errors after history reopen (covered by e2e).

## Fixes (all 10 resolved, 2026-10-27)

1. **Triage** — `loop.py` matches bare `task`/`tasks` on a word boundary
   (`\btasks?\b`); "multitask" still falls through. Verified by
   `test_bare_task_problem_uses_task_tool`,
   `test_multitask_word_does_not_trigger_scheduler`, a new
   `investigate.spec.ts` e2e, and field trial T4 (now collects
   `get_scheduled_tasks`). Before/after:
   `docs/assets/fieldrook-m010-phantom-{before,after}.png`.
2. **Resolution label** — `resolutionOf()` now prefers the latest plan
   status (`RESOLVED — verified by measurement`,
   `UNRESOLVED — verified outcome: NOT_RESOLVED`,
   `INCONCLUSIVE — measurements insufficient`, `RESOLUTION <STATUS>`)
   before falling back to executions/proposals. E2e asserts the
   NOT_RESOLVED header text.
3. **Stepper stage** — `stageOf()` treats any plan as stage 3 Resolve.
4. **Stale assessment** — plan baseline and Confirm Fix rebuild the
   simulated assessment (same helper as M007 reverify) and log an
   "Assessment refreshed" activity. Verified by
   `test_assessment_refreshes_after_baseline_and_verify`; the after-walk
   resolution shot shows "3 of 3 evidence items usable".
5. **Historical clutter** — superseded evidence cards collapse the JSON
   preview into a "Superseded JSON — expand to compare" details block;
   header, flags, and Re-check stay visible. E2e + after-walk assert it.
   After shot: `docs/assets/fieldrook-m010-historical-after.png`.
6. **Stage navigation** — the stepper renders as buttons that smooth-scroll
   to the `stage-investigate` / `stage-understand` / `stage-resolve`
   anchors on the New investigation form / Incident overview / Action
   Center sections (matching the page's own stage eyebrows; a duplicate
   anchor set was removed so each id resolves once). E2e clicks through
   Understand → Resolve; the after walk does the same.
7. **Timeline rounds** — "Plan baseline:" / "Plan verification:" tool runs
   open "pre-fix baseline" / "Confirm Fix verification" rounds; tools
   within one run stay grouped, repeat runs open fresh rounds. E2e +
   after-walk assert the round heads.
8. **Badge tooltips** — header badges explain reasoning-engine mode vs
   host capability; per-investigation badges explain that
   investigation's evidence source and engine.
9. **Search debounce** — knowledge free-text search debounces 250ms
   before hitting `GET /api/knowledge`.
10. **Focus styles** — `:focus-visible` outline in the accent color for
    links, buttons, inputs, selects, textareas, summaries, and tab stops.

## Field trials, post-fix (simulated + fixtures, 2026-10-27)

| Trial | Problem | Latency | Tools | Bad cites |
| ----- | ------- | ------- | ----- | --------- |
| T1 crash | Excel closes on one workbook | 0.13s | app crashes, event logs | 0 |
| T2 service | wuauserv healthy? | 0.04s | process, service details, event logs | 0 |
| T3 DNS | nothing resolves | 0.04s | dns config, dns test | 0 |
| T4 task | phantom task safe to disable? | 0.05s | **scheduled tasks**, event logs | 0 |
| T5a/b worker | demo worker down, twice | 0.04/0.03s | demo-worker health | 0 |

T5b matched 2 library entries (strength 8, signals symptom×3 +
category + evidence). Contradiction + recheck counts: T2 surfaces 1
contradiction with 2 suggested rechecks; the rest are clean.

## Quality gate (2026-10-27)

- Backend pytest: **251 passed** (248 M009 + 3 M010 regression tests).
- Gauntlet: **47/47** (37 fixture/tool + 10 capped live `muse-spark-1.3`);
  raw JSON `backend/eval/results/20261027T113426Z.json` (gitignored).
- Frontend build (`tsc --noEmit && vite build`): clean.
- Playwright e2e: **17/17** (16 M009 + 1 bare-task triage test; the
  reopen selector was re-scoped to the heading after finding 2's label
  change made `getByText("Resolution workspace")` ambiguous).
- Audit after-walk: `AUDIT-WALK-DONE`, zero console/page errors, zero
  failed requests, all fix assertions green.
- Gitleaks working-tree scan: only the ignored `.env` and the
  documented harmless demo hash in `docs/jury-demo/index.html`.

## What remains / M011 candidates

- Gauntlet runner exit code flickers to 1 on some all-pass Windows runs
  (results JSON confirms the pass; shutdown/cleanup race, same family
  as the known pytest TEMP issue). Worth one flake-hunt session.
- Ports 8000/5173 were occupied by other processes during the audit;
  the audit ran isolated on 8123/5174.
- Live-machine rehearsal (fixtures off) is still manual; the audit
  stayed on fixtures + simulated model by design.
- Candidate M011: guided first-run onboarding, saved technician
  / per-host profiles, or export-to-ticket integrations.
