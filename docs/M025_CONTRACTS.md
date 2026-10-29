# M025 contracts v1 (frozen by lead — 2026-10-29)

Branch `m025/field-kit` from `master` 4b8a317. Three implementation
agents (ALPHA/BETA/GAMMA) work in self-created git worktrees on their
own branches; lead integrates; ZETA validates the integrated output.
Research wave (packaging ×2 + localhost security, all read-only with
cited bodies) backs every decision below.

## Toolchain (decided)

- PyInstaller **one-dir** for BOTH the collector exe and the desktop
  backend. Rationale: mature hooks (fastapi/pydantic/uvicorn),
  fastest iteration, no per-launch unpack cost, smaller
  AV-heuristic surface than one-file. No .NET rewrite (contract
  bar from FORGE §2 stands).
- Build pins live in the build scripts; a build BOM (tool +
  version + artifact hashes) is part of the release docs.
- No code signing (not authorized); state it in the release docs.
- Collector exe is a **console** exe (consent screen must be
  visible). Desktop backend console decision is BETA's, with the
  hard rule: startup/shutdown errors must be visible AND logged to
  `%LOCALAPPDATA%\FieldRook\logs`.

## Runtime contract (BETA)

- One process: uvicorn serves FastAPI + the Vite production `dist`
  at `/` via `StaticFiles(html=True)` mounted AFTER all `/api/*`
  routers. No frontend code changes needed (relative `/api/*`
  URLs verified; the only absolute URL in `frontend/src` is a help
  string in ServiceWorkstation.tsx:79, owned by GAMMA).
- `GET /` serves `index.html` when dist is present, else the JSON
  tagline (dev-API mode). `/api/status` is THE health signal.
- Bind `127.0.0.1:8000` by default; new `FIELDROOK_PORT` env
  override; **refuse non-loopback bind at startup**.
- Frozen-aware paths in ONE new helper (`backend/app/paths.py`):
  app dir (`sys._MEIPASS` vs repo), user data dir
  (`%LOCALAPPDATA%\FieldRook`, existing `FIELDROOK_DB_PATH` /
  `FIELDROOK_DEMO_STATE` overrides preserved).
- Fix before freeze: worker-script path override, `.env` load
  location (never repo-root by default), collector `sys.path`
  insert guard. Never default to or migrate the dev database.
- Single instance is launcher-owned (lock file or port probe) with
  a readable "already running" message. Launcher PID-tracks the
  server, kills only its own tree, and stops the detached demo
  worker via the existing fenced kill path.
- No bundled model, no secrets in artifacts, no admin required,
  localhost-only, no silent cloud.

## Security contract (BETA implements, ZETA verifies)

- Minimal set only: Sec-Fetch-Site enforcement in
  `LocalOriginMiddleware`, `TrustedHostMiddleware` for the
  localhost set, startup non-loopback refusal. No auth redesign;
  per-boot token stays deferred. Update affected headerless-post
  tests with a documented reason.

## Collector contract (ALPHA)

- `FieldRook-Collector.exe`, same `collect|validate` CLI, same
  exit codes, same consent double-gate. ZIP format FROZEN
  (FORGE_CONTRACTS §2): exe-produced packages must pass the
  existing roundtrip/verify tests byte-compatibly. No new format,
  no auto-transmit, no services, no admin required (report
  honestly when a category needs more).
- Deliverable: `packaging/collector/` (build script + spec
  inputs), portable dist dir, checksums, frozen smoke test.

## First-run / docs contract (GAMMA)

- New files only under `frontend/src/forge/` (`FirstRun*`); may
  edit `App.tsx` SOLELY to mount the first-run gate, and may
  reword the ServiceWorkstation.tsx:79 help string. No other
  frontend edits.
- Docs: new `docs/FIELD_KIT.md` (technician guide: install/remove,
  first run, collector journey, providers, offline capabilities)
  + `docs/DISTRIBUTION.md` standalone section planned→delivered.
  No other doc edits (lead owns release notes).
- Content honesty: no small-model CPU-responsiveness claims, local
  AI optional, cloud needs consent, offline stays useful.

## Ownership (files)

- ALPHA (`m25/alpha-collector-exe`): `packaging/collector/**`,
  `collector/**` ONLY for frozen-compat fixes (hidden imports,
  console flash; zero behavior change),
  `backend/tests/test_collector_frozen.py` (new).
- BETA (`m25/beta-desktop-runtime`): `backend/app/main.py`,
  `backend/app/paths.py` + `backend/app/version.py` (new),
  `backend/app/security.py`, `backend/app/config.py`,
  `backend/app/actions/demo_worker.py`,
  `backend/app/routers/collector_import.py`, `packaging/desktop/**`,
  `backend/tests/test_desktop_*.py` (new), `VERSION` (new, e.g.
  `0.4.0`). NO frontend files.
- GAMMA (`m25/gamma-first-run`): `frontend/src/forge/FirstRun*`
  (new), `frontend/src/App.tsx` (mount-only),
  `docs/FIELD_KIT.md` (new), `docs/DISTRIBUTION.md` (standalone
  section only).
- Everything else is lead-owned. Needing an unlisted file is a
  reported blocker, not a grab.
- Each child: worktree `C:\tmp\m25-wt-<agent>`, branch above
  forked from `m025/field-kit`, commits on own branch, pytest
  gate green (`FIELDROOK_OFFLINE` unset, `TEMP` redirected per
  repo memory), frontend build green if touched, secret scan on
  new files. No new production deps without lead approval.

## Integration order (lead)

ALPHA → BETA → GAMMA onto `m025/field-kit` with the full gate
after each merge. ZETA validates the integrated branch
(clean-env, security, privacy, roundtrips) before the M025
delivery commit. No push; no M026.
