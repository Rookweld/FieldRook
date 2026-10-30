# M026 contracts v1 (frozen by lead — 2026-10-30)

Branch `m026/desktop-rebirth` from `m025/field-kit` @ `8870d19`.
Four implementation agents work in pre-created worktrees on their own
branches; lead integrates; ZETA validates the integrated output.
Design source of truth: `FieldRookDesign/fieldrook_motion_lab/`
(`index.html` prototype + `DESIGN_HANDOFF.md` + both approved previews),
committed on this branch. The prototype is simulated UI, NEVER pasted
wholesale: extract tokens, components, and motion primitives only.

## Baseline facts (verified by lead recon)

- .NET 10.0.400 SDK present; WebView2 Runtime 156.0.4314.50 installed.
- Frontend: tab state in `App.tsx` (`problem|service|history|knowledge`,
  no router), `api.ts` typed client, `forge/FirstRunGate` onboarding,
  14 Playwright specs (real backend :8123 + Vite :4173, isolated DB).
- Backend: FastAPI, 7 routers, `/api/status` = `{service, runtime,
  version}`, 45 backend test files, 684-test gate green on M025.
- M025 frozen server (`FieldRook-Server.exe`, PyInstaller one-dir) is
  KEPT: the native shell hosts it as a child process. No Electron.

## 1. Shell ↔ backend lifecycle (ALPHA owns, all rely on)

- Shell spawns the packaged `FieldRook-Server.exe` as an
  application-owned child (loopback only; port: `FIELDROOK_PORT` or
  free-port discovery — ALPHA decides, documented).
- Health = `GET /api/status` with `service == fieldrook-api` AND
  `runtime == desktop` (M025 Z1 identity rule, unchanged).
- Shutdown kills ONLY the owned child PID after a command-line fence
  check (`FieldRook-Server.exe` in cmdline), then the demo worker via
  the server's `--stop-demo-worker` path. No orphan backend.
- Single instance: reuse the M025 lock file + TCP probe + identity
  check. A second launch focuses/explains instead of double-starting.
- WebView2 missing → native error dialog with install guidance (no
  crash, no silent browser fallback). Backend crash → native error +
  log tail from `%LOCALAPPDATA%\FieldRook\logs`.
- Investigations persist across restarts (existing SQLite path rules).

## 2. Shell ↔ React communication (ALPHA implements, GAMMA consumes)

- WebView2 navigates to `http://127.0.0.1:<port>/` (the same React UI
  the backend serves; no separate UI bundle).
- JS→native bridge is typed, minimal, allowlisted JSON messages
  `{op, id, params}` → `{id, ok, result | error}`. Allowed ops ONLY:
  `openFile` (.zip collector packages), `saveFile` (exports),
  `getVersion`, `windowControl` (min/max/restore/close, only if the
  shell draws custom chrome). No `eval`, no filesystem access beyond
  dialog results, no navigation outside loopback (block + log).
- Drag-and-drop of a `.zip` onto the window delivers the file path to
  the React importer through the same validated channel.
- Contract test: roundtrip each op in isolation; an unknown op and a
  path-traversal payload MUST fail closed (add tests).

## 3. Design tokens + component ownership (BETA owns tokens)

- Tokens live ONLY in `frontend/src/signalforge/tokens.css`, values
  VERBATIM from the Motion Lab `:root`
  (`--void #140914`, `--coral #ff7457`, `--lime #dfff67`, `--peach`,
  `--offwhite`, plum/aubergine family, etc.). No other file declares
  palette hexes; no cyan revival, no rainbow accents.
- BETA owns `frontend/src/signalforge/**` (tokens, views, components),
  `App.tsx` (nav restructure), all component CSS, FirstRun CSS only.
- Views: `signalforge/views/Launchpad`, `Workbench` (+ Evidence,
  Knowledge, Settings restyles). Launchpad shows REAL recents/status;
  never fictional investigation records; FirstRunGate stays mounted.
- Workbench answers WHAT IS WRONG / KNOW / NEXT / WHY / HAPPENED from
  typed props. Motion Lab percentages/counters/narratives are
  placeholders and MUST NOT ship as measurements; unknowable values
  get truthful labels or are omitted.
- Footer milestone label becomes M026.

## 4. Motion + activity state (DELTA owns primitives)

- Primitives in `frontend/src/signalforge/motion/`: `CircuitVeins`
  (SVG stroke-dashoffset pulses, 13–18 s), `SignalTrace` (ECG travel,
  4.8 s), instrument orbits (20–70 s), hover elevation (150–200 ms).
  CSS/SVG + composited transforms only; no JS rAF loops.
- Preference key `fieldrook.motion.v1` ∈ `alive|quiet|off`
  (prototype values: `ambient|quiet|off` — DELTA maps and documents),
  persisted locally, `body[data-motion]` switch,
  `prefers-reduced-motion` → off. Quiet damps, Off kills all decor.
- The signal trace is ORNAMENTAL: it may react to bounded real app
  activity (navigation, panel expand, action confirm) but MUST NEVER
  be labeled as CPU/network/health/AI telemetry.
- No animated décor behind long-form reading; ambient effects damp
  automatically in work-heavy views. No permanent high-CPU loops;
  measure on real hardware and report numbers.

## 5. Navigation + investigation state (BETA shapes, GAMMA wires)

- View state `{view: launchpad|workbench|evidence|knowledge|settings,
  investigationId?}` replaces the 4-tab model; deep behaviour
  (seed/open investigation, error boundary reset) is PRESERVED.
- BETA builds views against typed props from REAL `api.ts` shapes.
  GAMMA connects them via NEW `frontend/src/signalforge/hooks/**`
  and may edit BETA view files ONLY to add hook calls + prop
  passing (zero markup/CSS changes). BETA must not invent data
  fetching; GAMMA must not restyle. Friction → lead decides.
- Investigation lifecycle, Collector import + validation, evidence
  provenance, knowledge citations, provider selection, simulated/
  offline modes, approval/execution split, cancellation,
  resolution/verification, export, persistence: ALL preserved, all
  wired to real endpoints. No capability quietly dropped.
- `api.ts` may only be EXTENDED (no signature breaks); backend
  changes need a lead-approved blocker report first (prefer none).

## 6. Build, packaging, distribution (ALPHA + lead)

- `dotnet publish` (ALPHA justifies self-contained vs
  framework-dependent) + existing PyInstaller server + `vite build`.
- Portable layout: `FieldRook.exe` (shell) beside `server/` (frozen
  backend incl. UI).
- Release version `0.5.0`: `VERSION` file stays the single source;
  assembly metadata MUST match (verified in ZETA).
- Extend `SHA256SUMS.txt` + `BOM.txt` with shell provenance
  (SDK version, WebView2 requirement, publish mode). No signing
  (not authorized). Required runtimes documented honestly.
- Collector portable distribution is preserved untouched.

## Worktrees, branches, execution rules

- `C:\tmp\m26-wt-alpha` (`m026/alpha-shell`), `-beta`
  (`m026/beta-visual`), `-gamma` (`m026/gamma-wiring`), `-delta`
  (`m026/delta-motion`); lead integrates onto `m026/desktop-rebirth`
  (`C:\tmp\m26-wt-lead`). ZETA validates the integrated tree.
- Each agent: stay inside its worktree, commit ONLY its own branch,
  never touch `C:/dev/FieldRook` (operator checkout). Backend pytest
  via `C:/dev/FieldRook/backend/.venv` python with cwd set to the
  OWN worktree backend + `PYTHONPYCACHEPREFIX` redirected +
  `-p no:cacheprovider`. `FIELDROOK_OFFLINE` unset for backend
  pytest; `TEMP`/`TMP` redirected per repo memory. Frontend:
  `pnpm install` inside the own worktree first.
- Long runs: supervised detached execution with out/err/pid/exit
  markers (see `.fieldrook-tmp/run_detached.py` pattern); record
  exact exit codes; never Ctrl+C a session to manage subprocesses;
  never stop/kill unverified processes.
- Per-agent gates before reporting done: own tests/build green
  (pytest targeted / `tsc --noEmit` + `vite build` / `dotnet
  build`), secret scan on new files, no new production deps
  without lead approval. Report: commits, what works, exit codes,
  blockers, deviations from these contracts.
- Needing an unlisted file is a reported blocker, not a grab.
