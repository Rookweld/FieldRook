# FieldRook distribution reality (M024.1)

## Status: development launcher, not a standalone release

`start-fieldrook.bat` starts two DEVELOPMENT servers from a source
checkout: uvicorn on `127.0.0.1:8000` and `pnpm run dev` (vite,
default port 5173). It requires, on the machine that runs it:

- a Python that can create `backend/.venv` plus the installed
  requirements (`pip install -r requirements.txt`),
- Node.js + pnpm plus installed `frontend/node_modules`,
- free ports 8000 and 5173.

There is no frozen build, no installer, and no standalone
executable. Do not describe the `.bat` as a release.

## Verified behavior (M024.1-5, test-port replica)

Verified with an identical-logic copy on backend :8131 /
frontend :5131 plus a scratch DB, so the operator's :8000
stack was never touched.

| condition | observed behavior |
|---|---|
| happy path | backend API live, frontend HTTP 200. Note: vite binds `::1` (IPv6 loopback) by default; `localhost:` URLs work, a literal `127.0.0.1:` frontend URL does not. |
| `backend/.venv` missing | clear error + remediation command, exit 1. |
| `frontend/node_modules` missing | clear error + remediation command, exit 1. |
| pnpm missing | NOT checked. The frontend window shows `'pnpm' is not recognized as an internal or external command` and closes; the launcher has already printed success. |
| Python missing | the venv check fires, but the printed remediation (`python -m venv ...`) itself fails with `'python' is not recognized...`. |
| backend port occupied | launcher prints "both windows launched", exit 0. Backend fails with `[Errno 10048] ... only one usage of each socket address ...` in a window that closes immediately; frontend still serves. Split-brain with a success message. |
| one server fails (general) | same: no health check, no log file, no non-zero exit. The `start`ed windows close on process exit, so the error text is visible only while the window is open. |

Consequences for anyone running the launcher:

1. A failure can look like a success. Always check that BOTH
   `http://127.0.0.1:8000/api/status` and the frontend URL
   respond; the launcher's own output proves nothing.
2. Ports are fixed. If 8000 or 5173 is taken (including by
   another FieldRook instance), the backend fails and the
   frontend may silently move to another port (vite default).
3. Error text is ephemeral. Re-run the failing half manually
   in a persistent terminal to read it:
   `backend/.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
   or `cd frontend && pnpm run dev`.

## Standalone packaging route (delivered by the M025 Field Kit track)

The M025 Field Kit replaces the two-server development launcher above
with a single-process desktop runtime plus a frozen Collector
executable. Technician-facing guide: `docs/FIELD_KIT.md`. Scope note:
this section describes the integrated M025 runtime; it is written on
the first-run/docs branch, and clean-machine runs are validated on the
integrated branch by ZETA — nothing here claims a clean-machine result
observed from this branch alone.

Delivered shape (per `docs/M025_CONTRACTS.md`):

1. Frontend served from the backend. The Vite production `dist` is
   mounted at `/` via `StaticFiles(html=True)` after all `/api/*`
   routers: one process, one port, one health signal (`GET
   /api/status`). `GET /` serves `index.html` when dist is present,
   else the JSON tagline (dev-API mode).
2. Frozen backend + collector. PyInstaller one-dir for both the
   desktop backend and `FieldRook-Collector.exe` (same
   `collect|validate` CLI, exit codes, and consent double-gate; the
   ZIP format is frozen, so exe-produced packages pass the existing
   roundtrip/verify tests). The collector is a console exe so the
   consent screen stays visible. No Python/Node on the target
   machine; no admin required; builds are unsigned (stated, not
   hidden).
3. Per-user data dir. DB, imported packages, and logs live under
   `%LOCALAPPDATA%\FieldRook`, never beside the exe and never in a
   dev checkout. `FIELDROOK_DB_PATH` / `FIELDROOK_DEMO_STATE`
   overrides are preserved; the dev database is never defaulted to
   or migrated.
4. Single-instance guard. A second launch reports "already running"
   instead of the old 10048 flash-and-close.
5. One bootstrapper. Starts the server on the single localhost port
   (`127.0.0.1:8000` by default, `FIELDROOK_PORT` override; a
   non-loopback bind is refused at startup), opens the browser,
   offers the first-run provider/consent tour, and shuts down cleanly
   — PID-tracked, killing only its own tree, stopping the detached
   demo worker via the existing fenced kill path.
6. Release hygiene, carried over from M020: no API keys, no `.env`,
   no personal investigation data in the artifacts; no model
   downloads without consent; no admin required; localhost-only bind
   by default.

The M024.1 failure-mode table above stays as the historical record
for `start-fieldrook.bat` (source-checkout development path). For
the Field Kit runtime the corresponding checks are: exactly one
localhost port answers (`/api/status`), and startup/shutdown errors
are both visible on screen and logged to
`%LOCALAPPDATA%\FieldRook\logs`.
