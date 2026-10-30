# M026 Delivery — Native Desktop, Visual Renaissance & Motion System

- **Branch:** `m026/desktop-rebirth` (local; NOT merged to master, NOT pushed)
- **Base:** `m025/field-kit` @ `8870d19` (M025 delivery manifest)
- **HEAD at delivery:** `c45ccc4` (see commit map; delivery doc commit follows)
- **Version:** 0.5.0 (single source: `VERSION`)
- **Date:** 2026-10-30
- **Verdict:** RELEASE-READY per ZETA-2 confirmation (all fixes verified,
  G2 47/47 independently reproduced, journey proven in the shipped
  bundle). No push/publish/sign performed — awaiting authorization.

## Commit map

Agent work (all based on `8870d19` + shared `40707ff` design reference):

- `m026/alpha-shell` @ `d176290` — native WPF+WebView2 shell, lifecycle,
  packaging (`Build-Shell.ps1`), hardening (6 commits).
- `m026/beta-visual` @ `631dd49` — SIGNALFORGE views/shell/nav, palette
  scrub to tokens, frame/hero/rail/a11y fixes (5 commits).
- `m026/gamma-wiring` @ `909d001` — hooks, shell bridge client, API
  extensions, backend-surface pins, WIRING-GUIDE (4 commits).
- `m026/delta-motion` @ `fd7bcf3` — motion primitives, prefs wiring,
  off-mode scoping, measured numbers (3 commits).

Lead integration (merges BETA `c2f332f`, GAMMA `1d2755c`, DELTA
`dcfce9f4`, ALPHA `ca5224a`, oldest-first):

- `3f5f599` — wiring, bridge conformance, persisted nav, VERSION 0.5.0,
  E2E seed + launchpad spec, FirstRun copy, disposal of unreferenced
  History/Header/Atmosphere.
- `7bc8455` — Build-Shell records refreshed zip hash in BOM shell block.
- `6fde008` — ZETA fix batch: BLOCKER-1 stable engine key, MAJOR-1 nav
  scoping, MAJOR-2 relabel, MINOR-1/2/4.
- `f213094` — scope 3 E2E assertions past tile echoes (G2 47/47).
- `c45ccc4` — MINOR-2 cascade fix (drop losing transparent override).

## Implemented features by agent

**ALPHA — native shell** (`native-shell/`, `packaging/desktop/`):
WPF + WebView2 host; owned-child backend lifecycle (spawn, health-gate
on desktop-identity `/api/status`, PID-fenced shutdown, no orphans);
single-instance named mutex with dialog + exit 0; explicit
CreateJobObjectW entry point; WebView2-missing graceful shutdown;
`Build-Shell.ps1` (self-contained win-x64 single-file default,
FrameworkDependent opt; WebView2 SDK 1.0.4314.35) integrating
`FieldRook.exe` beside `server/`, refreshing the zip + SHA + BOM shell
provenance; README-SHELL.

**BETA — visual renaissance** (`frontend/src/signalforge/`): SIGNALFORGE
design system; tokens.css verbatim from Motion Lab `:root` (no other
palette hexes, no cyan); Launchpad / Workbench / Evidence / Knowledge /
Settings views; SignalFrame shell (nav rail, evidence rail, status
bar); engine reskin to tokens; FirstRunGate integration; responsive
rules (rail collapses first); visible focus + keyboard support.

**GAMMA — functional integration** (hooks, bridge, API): `useViewState`
persisted nav, `useCollectorImport` consented import incl. window-level
`.zip` drop, `useGuidedChecks`; typed allowlisted bridge client
(`shellBridge.ts`: openFile/saveFile/getVersion/windowControl +
`fieldrook:file` push normalization, fail-closed); backend surface
pins; WIRING-GUIDE route map (old location → new location) that drove
lead integration and the E2E migration.

**DELTA — motion & accessibility** (`motion/`, prefs): CircuitVeins +
SignalTrace (CSS/SVG composited, zero JS rAF loops); Alive/Quiet/Off
profiles persisted under `fieldrook.motion.v1`, `body[data-motion]`,
RDM → off; MotionSwitcher in Settings; measured idle numbers;
off-mode descendant scoping.

**ZETA-1 / ZETA-2 — independent validation:** full gates on the
integrated tree + shipped bundles; found BLOCKER-1 (remount), MAJOR-1
(selectors), MAJOR-2 (label), MINOR-1..4; re-verified every fix on the
final bundle incl. direct-adoption proof, 21 fresh screenshots, and a
release verdict. Reports: session records (ZETA-1 full gate table,
ZETA-2 confirmation); evidence under `.fieldrook-tmp/m26-zeta{,2}/`.

**LEAD — architecture & integration:** contracts doc
(`docs/M026_CONTRACTS.md`), merge order + conflict resolution, App.tsx
unification, bridge conformance (openFile bytes / saveFile base64 /
getVersion top-level version / push normalization, unit-tested both
sides), VERSION 0.5.0 single-source cutover, E2E seed + migrations,
artifact builds + manifest coherence, all ZETA findings resolved,
delivery checkpoint.

## Native architecture

```
FieldRook.exe (WPF + WebView2, self-contained win-x64)
  └─ spawns FieldRook-Server.exe (PyInstaller one-dir, child)
       ├─ serves frozen React UI (frontend/dist) + FastAPI
       ├─ loopback-only; health = /api/status {service,runtime,version}
       └─ on shell close: fenced stop of owned PID only → no orphans
Bridge:  {op,id,params} → {id,ok,result|error}; allowlisted ops only
Drop:    window .zip drop → confirm → consented import → reseed+remount
Data:    per-user LOCALAPPDATA dir; isolated ports/DB in tests
```

Single-instance via named mutex; occupied :8000 by a live Desktop
refuses with AlreadyRunning (exit 3, foreign untouched); WebView2
absent → native dialog + backend shutdown + exit 1 (code-reviewed).

## Working app + build outputs

Built from a clean worktree (`C:\tmp\m26-wt-build4` @ `c45ccc4`) via
`build.ps1` then `Build-Shell.ps1` into a fresh out dir:

- **Bundle:** `FieldRook-0.5.0/` + `FieldRook-0.5.0.zip`
  (84.5MB) + `SHA256SUMS.txt` (4/4 verified) + `BOM.txt`
  (commit `c45ccc4` == HEAD, shell provenance + refreshed zip line).
- **Native shell:** `FieldRook.exe` 134.8MB, self-contained win-x64
  single-file, assembly 0.5.0, sha256 `8924f2f3c882…` (unchanged
  since first integration — no native-code deltas after ALPHA).
- **Frozen server:** `server/FieldRook-Server.exe`, `--version` 0.5.0,
  sha256 `aa1fd7a31f05…`; worker `e22067760a3a…`; zip `6b97ef8920fd…`.
- **Build provenance:** clean worktree @ `c45ccc4`, builder Python
  3.14.3, PyInstaller 6.22.3 (pinned), dotnet SDK 10.0.400, WebView2
  SDK 1.0.4314.35; signing NONE (not authorized). Retained at
  `.fieldrook-tmp/m26-dist4/` (operator paths; ship the zip).

Prior verified bundles (evidence retained): `m26-dist` @ `7bc8455`,
`m26-dist2` @ `6fde008`, `m26-dist3` @ `f213094` (all SHA 4/4 at build).

## Test results (all exit codes verified)

| Gate | Command / runner | Exit | Result |
|---|---|---|---|
| Backend pytest | venv `pytest tests -q` (ZETA-1 G1) | 0 | 684 passed, 4 skipped (collector-exe env skips) |
| Playwright E2E | `pnpm exec playwright test` (lead + ZETA-2 G2) | 0 | **47 / 47** (2.2–2.4m; was 7/47 pre-fix) |
| Diagnostic Gauntlet | `eval.run` fixtures (ZETA-1 G3) | 0 | 37 / 37 (0 live-model) |
| .NET shell tests | `dotnet test -c Release` (ZETA-1 G4) | 0 | 66 / 66 |
| Frontend build | `tsc --noEmit && vite build` | 0 | 107 modules; dist hashes identical to frozen bundle |
| Frozen smoke | native exe cold/min/max/restore/2nd-instance/close (G6) | 0 | window ops pass, 0 orphans, lock+port released |
| `--smoke` | exe self-check + fenced stop | 0 | spawn→healthy(desktop/0.5.0)→stop, no orphan |
| Default-port refusal | exe vs foreign :8000 occupant | 3 | AlreadyRunning by design, foreign undisturbed |
| API journey | 10-step frozen-server journey (G7) | 0 | 10/10 (import 3→13, 400s, export, followups) |
| UI journey direct | intake→adopt, no workaround (ZETA-2 G7) | 0 | 7/7 + persist/restart 1/1, real export download |
| Motion/a11y | switch/persist/RDM/keyboard/narrow/cyan (G10) | 0 | 5/5 |
| Security live | 11 probes + 3 wrong-machine + secrets sweep + SHA | 0 | 11/11, 3/3, 86 files/1 benign hit, 4/4 hashes |
| MAJOR-2 literal | VERIFIED_RESOLVED label in bundle | 0 | "Open report export" pixel-proven |
| MINOR-2 s02 | tab-strip solidity re-check (lead, ZETA-2 spec) | 0 | computed bg opaque, blur none, screenshot viewed |

## Screenshots + video

Real-app captures only (no Motion Lab substitution):

- ZETA-1 (`m26-zeta/shots/`, 19): native frame cold/maximized/
  second-instance, launchpad, intake/provider, workbench findings,
  evidence + timeline, import ready/imported, resolution,
  recents-export, settings-motion, reduced-motion, keyboard-focus,
  narrow-900, 1366.
- ZETA-2 (`m26-zeta2/shots/`, 21): re-captured cold/maximized,
  direct-adopted case, evidence/import/resolution/export/reload/
  restart, MINOR-1/2/4 + MAJOR-2 pixel proofs, G10 set.
- README set (`docs/assets/m026/`, copied at delivery): launchpad
  native, workbench case, evidence, import, settings-motion.
- Demo video (`docs/assets/m026/demo-journey.webm`): one real
  launchpad → investigate → evidence → recents pass (Chromium UI
  capture of the same build the shell hosts — the sealed WebView2 has
  no automation surface; labeled honestly wherever shown).

## Accessibility findings

- Keyboard: 12-tab traversal with visible `:focus-visible` rings (G10
  proof shot); skip link; deliberate focus/scroll after navigation.
- Motion: persisted Alive/Quiet/Off + `prefers-reduced-motion` → off;
  ornamental signals labeled ("not a live health measurement").
- Layouts: 1920×1080 → 1280×720 + narrow 900px without horizontal
  scroll (E2E pinned incl. 390px phone shell); rail collapses before
  workspace; frame fills stage height (no maximized letterbox).
- Honest labeling verified in pixels: simultaneous LIVE DIAGNOSTICS
  (host capability) + FIXTURES (case mode); "No desktop shell
  detected" in browser; wrong-machine 422 copy.

## Motion performance (measured, not estimated)

Cold launch healthy 7–8s / window 8–10s (loaded-machine 4–5s); warm
4.0s / 5.2s; idle Alive whole-tree 1.16–1.24% CPU / 383–385MB;
graceful close 1.4–1.8s (0 orphans); renderer 6 anims alive/quiet, 0
off, 0 longtasks all modes, heap flat 9.5MB. Sizes: exe 134.8MB, zip
84.5MB, server dir 53.4MB. (28-core machine; WebView2-GPU deltas need
real-technician-laptop confirmation — headless SwiftShader is the
worst case.)

## Security observations

Bridge unknown-op/traversal/bad-param fail-closed (unit + live);
loopback-only binding; origin/host guards; Collector atomic validation
+ consent; wrong-machine 422 intact; bundle secrets sweep clean (1
benign hit); no operator data in artifacts; operator LOCALAPPDATA
byte-identical post-validation; foreign :8000 holder never disturbed.
Unsigned binaries (not authorized) — checksums + BOM provenance ship
instead.

## Regressions found & fixed

- **BLOCKER-1** (lead integration seam): hero branch flip remounted
  the engine on Investigate → intake reset + orphaned case; 35/40 G2
  failures. Fixed with a stable `key="sf-engine"` in both branches
  (React moves the node). Proven dead in the shipped bundle.
- **MAJOR-1:** 18 nav selectors scoped to Primary navigation (rail vs
  hero inline-link collision) + 3 content assertions scoped past tile
  echoes (view-panel / heading role / ancestor-section + exact text).
- **MAJOR-2:** "Export report" → "Open report export" (navigates to
  the resolve tab where downloads live).
- **MINOR-1:** stat values `overflow-wrap/word-break: normal`.
- **MINOR-2:** tab strip solid — took two attempts (a later skin rule
  re-transparentized it; removed the losing override, re-verified
  with ZETA-2's own spec + viewed pixels).
- **MINOR-4:** frame `height: calc(100vh - 52px)` + 700px floor.
- **Manifests:** Build-Shell re-zips before the BOM append and records
  the refreshed zip hash with a supersede note; BOM commit == tree
  HEAD on every delivery build.

## Remaining limitations (honest gaps)

- WebView2-absent path: code review only (runtime present everywhere
  here; uninstalling forbidden).
- Bridge live (dialogs, drag-drop, windowControl): unit + review only
  (no WebView2 automation surface exists).
- Free-port discovery vs non-desktop :8000 occupant: unit-covered,
  not exercised live (foreign owns :8000); desktop-keep branch
  verified live (exit 3).
- Per-mode CPU inside WebView2 proper: deltas measured in Chromium
  (same Blink); whole-tree idle measured on the real shell.
- Live-model providers + live diagnostics: intentionally unexercised
  (no keys; read-only safety).
- Elevated Collector categories excluded by design; multi-machine /
  upgrade / AV acceptance unvalidated; unsigned binaries.
- ALPHA alive/quiet CPU needs real-GPU laptop confirmation.

## Public materials (prepared, NOT published)

- `docs/M026_README_DRAFT.md` — full README redesign (§14), awaiting
  approval; screenshots wired to `docs/assets/m026/`.
- `docs/M026_DISCORD_DRAFT.md` — announcement + technical follow-up +
  posting order + dev insight (§15).
- No push, release, Discord post, or asset publication performed.

## Recommended merge/release sequence

1. Review this doc + README/Discord drafts + screenshots/video.
2. Approve replacing `README.md` from the draft (separate commit).
3. Merge `m026/desktop-rebirth` → master (local), tag `v0.5.0`
   (unsigned); push + publish only with explicit authorization.
4. Post Discord showcase per the draft order after the repo is public.
5. Follow-ups: technician-laptop GPU perf, WebView2-absent live test,
   signed build authorization, `:8000` non-desktop discovery live test.
