# FieldRook Diagnostic Gauntlet — Evaluation Report

## Methodology

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
- Live tier is small (3 cases, spending-capped) and uses fixture
  diagnostics; live-machine variance is covered by manual rehearsal instead.
- Content signals are substring checks, not semantic grading — they catch
  regressions, not subtle reasoning errors.
- No adversarial prompt-injection cases yet; the tool registry remains the
  enforcement boundary (covered by unit tests, not the gauntlet).
