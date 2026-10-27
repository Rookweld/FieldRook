# M012 UX Audit — first pass (2026-10-27)

Baseline: `469f374`, stack on :8123/:5174 (fixtures + simulated).
Screenshots: `.fieldrook-tmp/m12base/` (not committed).

## Measured baseline

- Investigation result page: **5207px** tall at 1440px wide; with a
  baselined plan: **6461px**. One scrolling document of 13 stacked cards.
- Diagnosis of the same assessment repeats 3×: Incident overview
  (leading hypothesis + next step) → Investigation progress (uncertainty
  pointer) → Diagnosis (full text). The criteria table, runbook, and
  timeline repeat evidence references again.
- Evidence renders as stacked JSON blocks by default (500-char preview +
  Full JSON). The evidence peek overlay also shows raw JSON.
- Pending state for 15–45s live runs: only a button label change plus
  one muted line ("Watch the activity timeline below" — but no timeline
  exists yet, since the request is still in flight).
- Color: INFERRED/MISSING/OBSERVED tags on nearly every line;
  FIXTURES + SIMULATED + header badges + likelihood chips compete.
  Ordinary metadata (counts, timestamps) uses alert-adjacent styling.
- Evidence chips (`ev-N`) open a fixed overlay; behavior is correct
  (no scroll jump) but the preview is JSON-first and takes no focus.
- History rows print id · timestamp · status · counts in monospace with
  no outcome emphasis; Knowledge rows reuse the `recheck` style.
- Resolve = two long sections (Action Center, Resolution workspace)
  with approve/execute/baseline/verify controls all visible at once.

## What must survive (capability inventory)

Intake form (3 templates, service select, screenshot + consent, fixture
toggle), blocking investigate + honest pending, follow-ups, reverify
with lineage + verdicts, contradictions, suggested rechecks, notes,
Worked Before (matches + hypothesis follow-up + regression rechecks +
save), approve/execute with one-time tokens + expiry resync, plans
(template/custom criteria, baseline, manual/execution interventions,
Confirm Fix, VERIFIED/NOT/INCONCLUSIVE), history + reopen, knowledge
CRUD + export, incident export, api-compat guards, redaction display.

## Redesign plan (second pass)

- Keep top tabs; add Findings / Evidence / Resolve sub-navigation
  inside an active investigation; collapse the intake form into a
  context bar with "New investigation".
- New result header: primary finding, status, key context, ONE next
  action. Merge Overview + Progress + Diagnosis repetition into
  Findings; keep every user-visible string the e2e suite asserts.
- Evidence: readable per-category summaries, JSON on demand;
  historical collapse stays; peek becomes summary-first with focus
  management and a deliberate "Go to full evidence" (tab switch +
  scroll).
- Resolve: staged presentation of proposals + plans + export; approve
  ≠ execute stays visually and functionally separate.
- Rewrite App.css as a token-based design system (restrained
  charcoal/slate/cyan/gold; green/red reserved for verdicts).
- Honest pending panel (elapsed time, no fake phases); React error
  boundary with recovery; responsive 1440/1920/1024/390; focus +
  reduced-motion support.

## Second pass — what was built (2026-10-27)

Screenshots: `.fieldrook-tmp/m12new/` (not committed); committed
before/after pairs in `docs/assets/fieldrook-m012-*`.

- **Views, not one document.** An active investigation now opens on
  **Findings** with **Evidence (n)** and **Resolve** one click away; a
  compact context bar (problem · id · time · status + New
  investigation) replaces the always-expanded intake form. Measured:
  the demo-worker result went from a 5207px single page to a 3013px
  Findings view + 1089px Evidence view + compact Resolve view.
- **Result header.** `OverviewPanel` rewritten: status pill
  (`resolutionOf`, unchanged strings), one primary finding, likelihood
  + evidence chips, coverage buttons that open Evidence, warnings, and
  exactly one computed next action (`nextActionFor`: approval →
  baseline → intervention → Confirm Fix → re-check → follow-up →
  export), which switches views and focuses its target.
- **Dedup.** ProgressPanel lost its repeated uncertainties block (the
  one list now lives in Diagnosis under "Unresolved questions");
  Diagnosis dropped the thrice-repeated id/timestamp line; runbook
  Why/Inspect/Confirms collapse into `<details>`; Worked Before shows
  the top match expanded and the rest collapsed.
- **Evidence.** New `evidenceSummary.ts` renders defensive per-category
  key/value rows (service, event, crash, process, OS, network, DNS,
  tasks, worker, error code, screenshot; truncated/unknown shapes fall
  back to the tool summary). Raw JSON moved into "Raw JSON" details;
  historical collapse, warnings, provenance, and re-check preserved.
- **Peek.** Summary-first (top 6 rows), source + timestamp on separate
  lines, focus moves to Close on open and restores on close, Escape
  still closes, "Go to full evidence" switches to the Evidence view
  and scrolls deliberately. Desktop side panel; bottom sheet ≤700px.
- **Resolve.** Same components and safeguards; before/after shows a
  one-line `BEFORE → AFTER · outcome` with full states in details;
  Execute uses a danger button distinct from Approve; verified
  outcomes read green via `badge-verified`/`verdict-pass`; the second
  "New resolution plan" demotes to ghost once a plan exists.
- **Landing.** Fixture control moved into an "Advanced" details block;
  templates, service select, screenshot + consent, and one gold
  Investigate button unchanged.
- **Pending + errors.** Blocking requests show an honest pending panel
  (elapsed seconds, no invented phases); a React error boundary
  catches render failures with recovery that preserves server-side
  data. Backend-down renders a red error card, never a black page
  (verified with the server stopped).
- **Design system.** `App.css` rewritten (~1650 lines, organized):
  charcoal/slate neutrals, cyan active/selection, forge-gold primary,
  green reserved for verified success, red failures, amber caution;
  type/spacing/radius tokens; sticky view nav; 1024/700 breakpoints;
  `:focus-visible` gold; `prefers-reduced-motion` disables animation.
- Footer bumped to Milestone 012.

## Third pass — six fixes from rendered review (2026-10-27)

1. Result header: likelihood pill + evidence chips wrapped onto stray
   lines — moved into the refs row.
2. Mobile top tabs wrapped mid-word — non-wrapping horizontal scroll.
3. Peek meta wrapped mid-timestamp — source and time on own lines.
4. Second "New resolution plan" competed with plan actions — ghost
   once a plan exists.
5. Diagnosis repeated id/timestamp a third time — removed.
6. Progress header repeated usable/failed counts — trimmed to
   re-check count (counts live in the result header).

## Fourth pass — final audit (2026-10-27)

- Scenarios A–F validated with screenshots: service lookup (wuauserv),
  crash finding, explicit ambiguity, scroll-stable preview + Escape,
  resolve flow, Worked Before with signals.
- Viewports: 1920×1080, 1440×900, 1024×768, 390×844 (+1152px e2e default);
  peek verified as bottom sheet on mobile.
- Full suite green: backend 252 passed, gauntlet 47/47 (37 + 10
  capped live `muse-spark-1.3`), `tsc --noEmit` + build clean,
  Playwright 21/21 (19 updated + 1 rewritten + 1 new next-action
  navigation test), Gitleaks clean apart from the two known findings
  (ignored `.env`, documented demo hash).
- Every e2e-asserted user-visible string survived; specs gained only
  view-switch clicks for the legitimate navigation change (plus the
  Advanced-details opener for the fixture toggle). No test deleted.
- Backend untouched: zero API/schema/behavior changes in M012.
