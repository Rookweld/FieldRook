# FieldRook Diagnostic Gauntlet — Evaluation Report

## M008 update (2026-10-27) — read this first

The gauntlet grew from 39 to **43 cases**: 23 investigation + 11 tool cases
in the deterministic fixture tier, and 9 capped live-model cases. New in M008:

- **Resolution probes**: three fixture cases drive plan → baseline → manual
  claim → verify through the API and assert the measured outcome
  (`VERIFIED_RESOLVED` after a synthetic fixture flip, `NOT_RESOLVED` when
  the worker stays failed, `INCONCLUSIVE` when the criterion tool errors),
  plus a non-empty baseline, an intervention-gated verify, an unchanged
  proposal set, zero executions, and valid citations after verification.
- **Live resolution flow**: `live-resolution-flow` investigates with the
  live model, then resolves via the API — honest `NOT_RESOLVED` with valid
  citations. No uncertainty is required here: an explicitly failed health
  read warrants a firm call (overconfidence wording still forbidden).
- **Hedge-aware `proven` check, widened again**: the live freeze case wrote
  "no system-wide freeze cause was proven" and "no proven system cause" —
  calibrated hedging the old patterns missed. The check now accepts
  "no ... proven" phrasings (still rejecting confident "no doubt ... proven";
  pinned by new assertions in `test_banned_claim_allows_hedged_proven`).

**Measured M008 results: 43/43 evaluated cases passed (34 fixture/tool + 9
live-model).** Raw JSON: `backend/eval/results/20261027T091434Z.json`
(gitignored; re-run with `python -m eval.run [--live]` from `backend/`).
The first live pass was 41/43: the two failures above (freeze `proven`
hedging, resolution uncertainty demand) were both measurement bugs, fixed
and re-run green — the gauntlet working as intended.

## M007 update (2026-10-27) — read this first

The gauntlet grew from 34 to **39 cases**: 20 investigation + 11 tool cases
in the deterministic fixture tier, and 8 capped live-model cases. New in M007:

- **Refresh probes**: three fixture cases post a real `/reverify` call and
  assert the verdict (`unchanged` on stable fixtures, `changed` on a
  synthetic Stopped → Running flip, `unavailable` when the fixture service
  vanishes), byte-identical historical preservation, exactly one added tool
  call, an unchanged proposal set (authorization boundary), and valid
  citations after the refresh.
- **Contradiction probes**: `mislead-net-down` now requires the deterministic
  contradiction record (adapters Up vs down report); new live case
  `live-contradiction-fixtures` holds the same bar under live reasoning.
- **Live re-check flow**: `live-recheck-flow` investigates with the live
  model, then re-checks via the API — verdict `unchanged`, history
  preserved, no proposals created.
- **Efficiency budgets**: `max_tool_calls` caps total spend per case
  (initial + runner reverify); citation checks now also cover refresh links
  and contradiction references.

**Measured M007 results: 39/39 evaluated cases passed (31 fixture/tool + 8
live-model).** Raw JSON: `backend/eval/results/20261027T075657Z.json`
(gitignored; re-run with `python -m eval.run [--live]` from `backend/`).

Notable live runs (all `mode=live`, zero proposals where forbidden):

- `live-network-fixtures` — 5 calls this time (vs 8 in M006): the reuse
  prompt lines measurably trimmed the sweep.
- `live-recheck-flow` — perfect 2-call triage, then API re-check `unchanged`.
- `live-contradiction-fixtures` — 2-call triage; contradiction record fires
  deterministically under live reasoning.
- `live-service-failure-fixtures` — contradiction record fires on the known
  wuauserv Running-vs-Stopped fixture gap instead of papering over it.

Genuine M007 findings from measurement:

1. The progress panel's first draft repeated full uncertainty strings and
   broke the scenario-A e2e strict-mode assertion — real duplication, fixed
   by listing missing-evidence needs with an uncertainty count instead.
2. Gitleaks (installed but not on PATH — now resolved) flags one historical
   `generic-api-key` hit in `docs/jury-demo/index.html`: 64-hex approval
   token *hashes* inside the static recorded replay. One-way hashes of
   expired single-use demo tokens, not credentials — false positive,
   documented here.

## M006 update (2026-10-27) — read this first

The gauntlet grew from 19 to **34 cases**: 17 investigation + 11 tool cases
in the deterministic fixture tier, and 6 capped live-model cases. New in M006:

- **Triage probes**: crash symptoms must route to `search_application_crashes`,
  DNS symptoms to `get_dns_config` + exactly one `test_dns_resolution` control
  query — `forbid_tools` fails any case that sweeps unrelated tools.
- **Service→process link**: service investigations must also call
  `get_process_info` with the service selector.
- **Continuity probe**: `followup-reuse-dns` posts a real follow-up and fails
  if it makes any new tool call.
- **Honest `proven` check**: bare "proven" still fails, but hedged forms
  ("not proven", "unproven", ...) pass — the old substring check punished
  calibrated hedging (found twice on `live-freeze-fixtures`, fixed in
  `run.py`, pinned by `test_banned_claim_allows_hedged_proven`).
- **Failure context**: failing cases now record the assessed text snippet in
  the results JSON so live-model verdicts can be audited.

**Measured M006 results: 34/34 evaluated cases passed (28 fixture/tool + 6
live-model).** Raw JSON: `backend/eval/results/20261027T063812Z.json`
(gitignored; re-run with `python -m eval.run [--live]` from `backend/`).

Notable live runs (all `mode=live`, zero proposals where forbidden):

- `live-dns-fixtures` — perfect 2-call triage: DNS config + one control query.
- `live-crash-fixtures` — crash search + error-code decode + process check.
- `live-service-failure-fixtures` — service details already bundle the 7023
  termination error, so the model correlated it without a separate event
  search; it also flagged the fixture's own Running-vs-Stopped inconsistency
  instead of papering over it.
- `live-freeze-fixtures` — first two runs tripped the old `proven` check on
  honest hedging ("causation is not proven"); passes after the check fix.

Genuine M006 findings from measurement:

1. The `proven` substring check punished calibration (fixed, see above).
2. Live `ExecutablePath` reads return empty without elevation (graceful,
   documented — not an error).
3. Live `CreationDate` arrives as `/Date(ms)/`, which the uptime parser did
   not handle — uptime was always null live. Fixed in `windows_proc.py`,
   pinned by `test_uptime_parses_powershell_json_dates`, verified live
   (svchost uptime 1043192s).
4. Fixture mirrors are per-tool, not a consistent world: the wuauserv process
   fixture says Running while the service fixture says Stopped. The live
   model noticed. Known limitation, documented below.

## Methodology (M005, still current)

The gauntlet (`backend/eval/`) runs realistic troubleshooting problems through
the real product path (HTTP API via TestClient, isolated temp database) and
scores each case against a documented reference answer (`cases.py`):

- **Tool selection**: required tools used (`must_use_all` / `must_use_any`).
- **Citation validity**: every fact/cause `evidence_ids` entry must resolve to
  a collected evidence item (checked programmatically, all cases).
- **Action discipline**: proposals required (`worker-failing`) or forbidden
  (every other case — including all insufficient-evidence cases).
- **Calibrated uncertainty**: uncertainties/missing-evidence required where
  the reference answer is "unknown"; overconfident language
  (`definitely|certainly|proven`) forbidden there.
- **Content signals** (`must_mention_any`): key entities in the assessment
  text (e.g. `phantom`, `2147942667`) — advisory, deterministic in fixture
  mode, best-effort for live-model wording variance.
- **Budgets**: tool-call counts recorded; the 8-call initial budget held.

Two tiers:

1. **Fixture tier** (16 cases): deterministic, no credentials, CI-safe.
   Simulated-analysis path with fixture diagnostics.
2. **Live-model tier** (3 cases, capped): real `muse-spark-1.3` reasoning over
   fixture diagnostics (isolates reasoning quality from machine state).
   Runner flags: `--live --max-live-cases N --sleep-s S`. Per-call token
   counts are NOT exposed by the provider responses, so latency and
   tool-call counts are recorded instead.

No baseline comparison against a plain LLM is claimed: without equal tool
and evidence access such a comparison would be misleading, and the gauntlet
measures FieldRook against its own references instead.

## Measured results — 2026-10-27 (staging, pre-M005-commit)

**19/19 evaluated cases passed (16 fixture + 3 live-model).**

| Case | Tier | Latency | Tools/calls | Result |
| ---- | ---- | ------- | ----------- | ------ |
| svc-stopped-manual | fixture | 0.17s | 2 | PASS — stopped+Manual not called a failure |
| svc-update-health | fixture | 0.04s | 2 | PASS |
| task-phantom | fixture | 0.04s | 2 | PASS — cadence cause + window-hiding + 2147942667 uncertainties |
| task-vague-cadence | fixture | 0.03s | 2 | PASS (after planner fix, see below) |
| net-vpn-drops | fixture | 0.03s | 3 | PASS |
| net-dns | fixture | 0.03s | 3 | PASS |
| insuf-freeze | fixture | 0.04s | 3 | PASS — no proposal, honest gaps |
| insuf-vague | fixture | 0.03s | 3 | PASS — declined to diagnose |
| mislead-healthy-worker | fixture | 0.03s | 1 | PASS — measurement beat user certainty, no proposal |
| worker-failing | fixture | 0.04s | 1 | PASS — exactly one AWAITING_APPROVAL proposal |
| svc-bogus-name | fixture | 0.01s | 0 | PASS — HTTP 400 |
| live-phantom-fixtures | live | 20.29s | 3 | PASS — found phantom + decoded error code |
| live-freeze-fixtures | live | 16.93s | 6 | PASS — honest unresolved, no proposals |
| live-network-fixtures | live | 22.75s | 8 | PASS — full network stack covered |
| err-hresult/err-win32/err-unknown/err-invalid/svc-invalid-name | tool | ~0s | — | PASS (5/5 direct-tool cases) |

Raw JSON: `backend/eval/results/20261027T032215Z.json` (gitignored; re-run
to reproduce: `python -m eval.run [--live]` from `backend/`).

## Genuine finding (fixed)

First run: **15/16** — `task-vague-cadence` ("Something seems to run every
hour") missed the scheduled-task tools because the planner only knew
`hourly`, not `hour`. Fixed by extending `SCHEDULED_KEYWORDS` with `hour`
and `recur`; re-run is 16/16. This is the gauntlet working as intended:
measurement found a real routing gap.

## Live-model observations (not failures)

- The model sometimes probes `get_demo_worker_health` off-topic (phantom,
  freeze cases). Harmless under the call budget; relevance tuning is future
  work, not a correctness defect.
- `live-network-fixtures` used the full 8-call initial budget — thorough
  here, but evidence that a relevance cap/truncation review is worthwhile
  before widening tool access.
- Live latencies 17–23s per investigation; acceptable for interactive use,
  worth showing as progress states (already in the UI timeline).

## Limitations

- Fixture tier scores the deterministic pipeline, not model quality.
- Live tier is small (9 cases, spending-capped) and uses fixture
  diagnostics; live-machine variance is covered by manual rehearsal instead.
- Content signals are substring checks, not semantic grading — they catch
  regressions, not subtle reasoning errors (`proven` is now hedge-aware).
- Fixture mirrors are per-tool snapshots, not one consistent machine state
  (e.g. wuauserv Running in the process mirror, Stopped in the service
  mirror). Cases assert per-tool behavior, never cross-tool consistency.
- No adversarial prompt-injection cases yet; the tool registry remains the
  enforcement boundary (covered by unit tests, not the gauntlet).
