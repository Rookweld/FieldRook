# M025 field-kit delivery manifest (release candidate 0.4.0)

Branch `m025/field-kit`. ZETA release audit passed; this file + the commit
that carries it are the M025 delivery checkpoint. No push, no signing
(neither authorized).

## Provenance

- Field-kit HEAD at ZETA fix: `a6d08f7` ("zeta desktop identity and
  version source"); delivery commit: see log (this file).
- Desktop bundle built clean-room from detached worktree @ `a6d08f7`
  (builder Python 3.14.3, PyInstaller 6.22.3 pinned, pnpm + Vite 6.4.5).
- Collector bundle built from detached worktree @ `a6d08f7` (same
  builder pins); BOM pins commit `a6d08f7`. `collector/` +
  `packaging/collector/` are byte-identical from `3b2ec5b` through
  `a6d08f7` (verified empty `git diff`).

## Packages (all SHA-256 independently re-verified)

Desktop 0.4.0 — `.fieldrook-tmp/desktop-dist3/`:
- `FieldRook-0.4.0.zip` (29,236,255 B)
  `a646e62318e5229311bfe4f5881cef2d03b0104b994ab0959315f838a363a11b`
- `FieldRook-0.4.0/server/FieldRook-Server.exe` (10,526,870 B)
  `f551765e98d80a56eb02b5b3396196d17ea50a751ac943c42c5548af3c1a69d`
- `FieldRook-0.4.0/server/_internal/demo-worker/fieldrook-demo-worker.exe`
  (2,095,742 B)
  `c8631cbe2f71f72f140269875aa351f055cec384925cd488b0fcb8340a11790e`
- Bundle dir 53.4 MB; zip holds 89 entries under one top-level dir;
  `SHA256SUMS.txt` + `BOM.txt` alongside (BOM pins commit `a6d08f7`).
- UI dist inside the bundle contains the GAMMA FirstRun code (verified).

Collector — `.fieldrook-tmp/collector-dist/FieldRook-Collector/`
(canonical pristine output; identical bytes also placed at the
git-ignored `dist/collector/FieldRook-Collector/` as the frozen-gate
fixture):
- `FieldRook-Collector.exe` (2,247,858 B)
  `1b921dd74b9ec86297973e368d44659315ed68389233d96c72b13f1e9f12557e`
- Bundle dir 18.1 MB; `SHA256SUMS.txt` (21 files) + `BUILD-BOM.txt`.
- Live behavior verified on the delivered exe: real `collect`
  (os/services/procs, exit 0) → `validate` (exit 0) → isolated backend
  import (200, 3 live evidence, hostname hashed, no leaks, 0 warnings);
  frozen gate 4/4 below.

## Identity and version (ZETA findings Z1/Z2, fixed in `a6d08f7`)

- `/api/status` answers `service` + `runtime` (`desktop` frozen |
  `dev` checkout) + `version`. Only a frozen Desktop runtime ever
  counts as "already running".
- The Desktop launcher treats a dev server on its port as a readable
  port conflict (exit 2, "development server"), enforces one Desktop
  per machine across ports via a fenced lock check, and never crashes
  on corrupt locks (fixed a `$Pid` automatic-variable collision that
  would have broken `-Stop`/shutdown paths).
- ONE version source: the `VERSION` file via `get_version()`. Verified
  agreement: `VERSION` = frozen `--version` = `/api/status.version` =
  launcher echo (`Desktop v0.4.0`) = BOM = `0.4.0`.

## Gates (every line exited 0; markers under `.fieldrook-tmp/`)

- Backend pytest full: **684 passed, 4 skipped** (`zeta-gate`, 173 s;
  ZETA rerun `zeta-gate2` confirms, skip names below).
- Targeted identity/version suites: 78 passed; 8/8 launcher CheckOnly
  identity probes pass (`zeta-targeted2`, `zeta-fence`).
- Playwright E2E (`pnpm test:e2e`, isolated backend :8123 + Vite
  :4173): **42 passed** in 2.7 min (`zeta-e2e`).
- Diagnostic gauntlet (`tests/test_gauntlet.py`): **38 passed**.
- Frontend build (`pnpm run build`, tsc + vite): exit 0, standalone
  and inside the desktop build.
- Desktop build (`packaging/desktop/build.ps1`): exit 0, frozen
  `--version` + bundled-worker smoke inside.
- Collector build (`packaging/collector/Build-Collector.ps1`): exit 0
  from field-kit; frozen gate (`tests/test_collector_frozen.py`):
  **4/4 pass** (help parity, consent refusal, sample validation,
  exe collect→validate roundtrip).
- Frozen journey (packaged exe, isolated port/data): **17/17**
  (`zeta-journey2`): status/identity/version, shipped-launcher
  already-check, UI served, investigation create, live collector
  import (3 evidence), retrieval, export (11,277 B), graceful
  shutdown, restart persistence, no bundle DB, isolated data, dev DB
  untouched (mtime+size proof), non-loopback refused (rc 1),
  occupied port refused (rc 1).
- First-run onboarding (frozen UI, human-like context): panel opens
  on first visit, "Start diagnosing" persists the marker, reload
  stays closed, reopen works — 1/1 with screenshots.
- Live dev-server proof: real dev backend probes as conflict
  (exit 2, "development server") — the operator's server can no
  longer be mistaken for Desktop.
- Secret scans (ZETA code + bundle docs + build inputs): clean.
- Operator safety: dev database byte-identical before/after; only
  audit-spawned PIDs were ever stopped (command-line fenced); all
  test ports verified closed afterwards.

Backend skips: the full runs reported 4 skips, all
`tests/test_collector_frozen.py` self-skips ("collector exe not built"
— the exe path was empty). ZETA then built the collector from
field-kit, placed it at the expected ignored path, and re-ran:
**4/4 pass**. Final state: **688 passed, 0 skipped** across the two
runs (684 + 4), every committed test executed.

## Deliberately unvalidated

- Code signing: not authorized; BOM states NONE.
- Elevated collector categories (`events`, `tasks`): excluded by
  design (need elevation); only `current_user_readonly` categories
  were exercised live.
- Multi-machine collector journeys, non-Windows platforms,
  upgrade-over-existing-install, AV-heuristic acceptance (one-dir
  rationale only, no vendor testing).
- Human-driven headed first-run click path (verified headless with
  a non-webdriver context + reviewed screenshots instead).
