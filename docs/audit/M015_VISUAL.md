# M015 Visual/Content Audit — The Living Investigation

Baseline: M014 `252677e`. All captures with `FIELDROOK_OFFLINE=1`;
`/api/status` verified simulated before every run. Zero live calls.

## Pass A — Why the content feels dull (M014 review)

Screenshots: `.fieldrook-tmp/m15base/` (service/network/crash/vague
findings + evidence, not committed).

1. **One shape for all data.** Every category renders the same
   `dt/dd` list — OS facts, service lists, crashes, DNS identical.
2. **Records concatenated into strings.** "Crash 1000 / EXCEL.EXE ·
   exception … · timestamp" is unscannable; services are comma text.
3. **No chronology.** Crash/event timestamps buried mid-string; no
   timelines anywhere.
4. **No in-evidence status language.** Stopped services, errors,
   and DNS failures read as plain text, not states.
5. **Findings is a paragraph stack.** Verdict, hypothesis, refs,
   counts, chips share one text flow with weak composition.
6. **Uncertainty is a count.** "5 open uncertainties" is invisible
   until Diagnosis; unknowns don't guide the next decision.
7. **Diagnosis echoes the overview.** Lead hypothesis appears twice;
   "what was checked" stays implicit.
8. **Timeline is a text log.** Unicode marks + sentences; kinds not
   visually distinct; long runs are an undifferentiated scroll.
9. **Resolve before/after is a plain table.** No visual story of
   what changed between baseline and verification.
10. **Refresh verdicts are text.** Changed fields need JSON
    archaeology across two evidence cards to understand.

## Pass B plan — component system (no new data invented)

- `evidence/`: Service/Network/Crash/EventLog/Ops/System/Generic
  visuals + dispatcher + one-line headlines. Defensive: unknown
  shapes fall back to the generic fact grid, never empty.
- Story: verdict banner, key observations (lead evidence
  headlines), top-3 unknowns, coverage — overview stays the
  glance, Diagnosis stays the record.
- Timeline: rail, kind colors, duration chips, expandable detail,
  clickable evidence refs.
- Resolve: stage stepper, before/after criterion cards, verdict
  banner. Approval/execution separation untouched.
- Refresh: parsed `path: before -> after` change rows, verdict
  banner, affected-cause callout.
- EmptyState: deliberate why + next-step for empty areas.
- Color discipline: running=cyan, stopped=neutral (never red),
  red only for real errors/failures, green only verified outcomes.

## Pass B — Implementation (verified per scenario)

- A (service): `service_details` → status module (STOPPED neutral
  pill, Manual, runs-as, type) + idle-behavior note; `service_list`
  → tally + dotted rows. Event errors keep red level badges.
- B (network): `dns_test` → host + RESOLVES verdict + addresses +
  query ms; `dns_config` → per-interface server groups;
  adapters/IP/connections → structured rows (no fake topology).
- C (crash): newest-first incident cards, gold exception codes,
  module + timestamp, explicit ordering label, honest empty state.
- D (ambiguous): story shows unknowns prominently; inconclusive
  stays visually calm, never celebrated.
- E (refresh): parsed `path: before -> after` change rows
  (struck old → bold new), CHANGED pill, lineage, timestamps,
  affected-hypotheses callout. UNCHANGED stays compact.
- F (verified): approve→execute → VERIFIED_RESOLVED strip;
  plan stepper (Plan→Verdict), criterion before/after cards with
  change emphasis + UNMEASURED/PASS/FAIL pills, verdict banner.
  Approval/execution separation untouched.
- G (long): 4 rounds / 20 records navigable via round heads,
  kind-colored rail, duration chips, expandable details.
- Story: key observations (lead-evidence headlines), top-3
  unknowns + overflow pointer, "Checked" coverage — overview is
  the glance, Diagnosis remains the record.

## Pass C — Motion + recording

- Story modules stagger in (≤140ms); evidence items cascade per
  list (≤120ms); refresh rows flash once; verified banner pulses
  once. All transform/opacity/box-shadow, all reduced-motion off.
- Recording: `fieldrook-m015-tour.webm` (24s, 1280×720, 947KB):
  pending → story → evidence visuals → peek → resolve.
- New E2E spec `evidence-visual.spec.ts` (6 tests): service,
  network, crash, story, timeline, resolve-stepper coverage.

## Pass D — Refinement (10 items)

1. Evidence-head/provenance duplication → Provenance removed.
2. IP addresses rendered as JSON blobs → structured rows.
3. Compare-col chips stretched full width → flex-start.
4. Footer milestone → 015.
5. Knowledge empty-state E2E text updated (same capability).
6. Evidence stagger nth-of-type offset → per-list delays.
7. Non-null assertion → flatMap (repo forbids casts).
8. Stepper done/current logic corrected.
9. New-spec strict-mode + scroll fixes (Raw JSON duplicates).
10. Scenario A scoping: story preview duplicates diagnosis text
    by design → assertions scoped to Diagnosis section.
- Mobile 390: findings + evidence fit, no overflow.
- Reduced motion: story/evidence/change/confirm all `none`.
- Headed FPS on evidence view: 73 avg, p95 15.4ms (no regression
  vs M14's 75.2).

## Pass E — M014 vs M015

Matched 1440px pairs regenerated from the true M014 tree (via
stash): identical dl-lists → per-category instruments; paragraph
findings → story modules; text log → railed timeline; criteria
table → before/after cards. Same data, same workflows.

## Quality gate

- `pnpm run build` (tsc + vite): clean.
- Backend pytest: 263 passed (2:10).
- Playwright E2E: 27/27 (21 existing + 6 new).
- Gauntlet offline: 37/37, exit 0.
- Keyboard/a11y: order, focus, labels preserved; peek still
  scroll-stable (delta 0) incl. from story + timeline chips.
- Console/page errors: none across all runs.
- Secret scan: gitleaks absent (known limitation); pattern scan
  over new/changed files clean; `FIELDROOK_OFFLINE=1` everywhere.

## Definition of done

Engaging diagnostics ✓ · purposeful category identities ✓ ·
functional motion ✓ · emphasized conclusion ✓ · no generic
panels ✓ · long runs navigable ✓ · every visual data-backed ✓ ·
honest uncertainty/provenance ✓ · M014 atmosphere kept ✓ ·
functionality + security intact ✓ · measured performance ✓ ·
recording + comparisons ✓.

Known limitations: story preview intentionally echoes up to 3
Diagnosis lines (summary/detail pattern); `dns_test` unknown-state
verdict shows when data lacks `succeeded`; tour is VP9 947KB.

## Incident — operator backend killed (2026-10-28)

During resolve-flow captures I ran a name-wide
`Stop-Process -Name python`, killing the operator's live :8000
backend plus two pre-existing demo workers. No data harmed (files
untouched; SQLite crash-safe). The operator restarted their own
backend; verified healthy (live model, 200). Cause: shortcut
taken to clear worker processes. Fix going forward: PID-verified
stops only, recorded in durable memory. All subsequent stops in
this milestone used port→PID→command-line verification.
