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

## Standalone packaging route (planned, NOT delivered)

Concrete route, in dependency order. None of this exists yet;
do not claim otherwise.

1. Serve the built frontend from the backend. `vite build`
   output mounted via `StaticFiles` removes the Node/pnpm
   runtime requirement AND the two-window split-brain: one
   process, one port, one health signal.
2. Freeze the backend + collector. Evaluate PyInstaller
   one-dir (or an equivalent) for `app.main` (server) and
   the collector entry point. Success criteria: runs on a
   machine with no Python/Node; `collector --help` works
   from the frozen exe; package import round-trips.
3. Per-user data dir. DB, imported packages, and logs live
   under `%LOCALAPPDATA%/FieldRook`, never beside the exe
   and never in the operator's dev checkout.
4. Single-instance guard. If the port is taken, refuse with
   a readable message instead of the 10048 flash-and-close.
5. One bootstrapper. Starts the server, opens the browser,
   first-run provider/consent choice, clean shutdown that
   kills only its own child processes (PID-tracked).
6. Release hygiene, carried over from M020: no API keys, no
   `.env`, no personal investigation data in the artifact;
   no model downloads without consent; no admin required;
   localhost-only bind by default.

Until (1)-(6) are built and tested on a clean machine, the
supported way to run FieldRook remains a source checkout
with the documented dev prerequisites.
