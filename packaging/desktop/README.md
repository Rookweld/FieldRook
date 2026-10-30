# FieldRook Desktop packaging (M025 BETA)

Frozen single-process desktop runtime: one uvicorn server serves the API +
the built UI on `http://127.0.0.1:8000/`, started and stopped by the
launcher. No Python/Node on the target machine, no admin, localhost only.

## Layout

```text
packaging/desktop/
  FieldRook.bat                 launcher bootstrap (execution-policy safe)
  FieldRook-Launcher.ps1        the launcher (env, single-instance, health wait,
                                browser open, PID-tracked shutdown)
  fieldrook-server-entry.py     frozen entry point (serve | --version |
                                --stop-demo-worker); also runnable unfrozen
  fieldrook-server.spec         PyInstaller one-dir spec (console ON)
  fieldrook-demo-worker.spec    PyInstaller one-dir spec (console OFF)
  build.ps1                     reproducible build (pins + BOM + checksums)
  README.md                     this file
```

Release bundle (`dist/FieldRook-<VERSION>/`):

```text
  FieldRook.bat / FieldRook-Launcher.ps1 / README.txt
  server/FieldRook-Server.exe + server/_internal/  (app, frontend-dist,
      VERSION, collector modules, demo-worker/fieldrook-demo-worker.exe)
```

## Launcher language: PowerShell + .bat bootstrap

The launcher is PowerShell 5.1 (ships with every supported Windows) with a
`.bat` bootstrap that applies a *process-scoped* execution-policy bypass, so
no machine setting changes. Why not a third frozen exe or plain `.bat`?

- Zero new dependency on the target: freezing a second Python launcher adds
  a third build + AV surface for no gain; PowerShell is already there.
- Plain `.bat` cannot do the contract UX: JSON health checks, TCP probes
  with timeouts, lock-file protocol, or tailing a log on failure.
- `.ps1` keeps the whole lifecycle readable and auditable by technicians.

Server console is ON (M025 toolchain decision): startup/shutdown errors are
visible in the window AND logged to `%LOCALAPPDATA%\FieldRook\logs`. The
worker console is OFF (detached by design; it logs to the demo-state dir).

## Runtime contract (what the launcher guarantees)

- Env setup: `FIELDROOK_PORT` (default 8000), `FIELDROOK_DB_PATH` and
  `FIELDROOK_DEMO_STATE` default into `%LOCALAPPDATA%\FieldRook` — explicit
  operator values always win, and the desktop NEVER defaults to a dev DB.
- Single instance: lock file (`fieldrook.lock`, launcher-owned) + TCP probe
  + `/api/status` identity check (service + runtime + version). Only a
  frozen Desktop runtime answers "already running" (browser reopens,
  exit 0). A dev server on the port is a readable conflict (exit 2, says
  "development server", suggests `-Port`); a foreign listener is a
  readable port conflict (exit 2). One Desktop per machine: a live
  Desktop on another port refuses ("already running on port N"). The bind
  itself is authoritative if two launchers race: the loser fails loudly,
  never split-brain.
- Health: polls `/api/status` (THE health signal) up to 90s, then opens the
  browser. On timeout it prints the server error-log tail and exits 1.
- Shutdown: kills ONLY its own server PID after a command-line fence check,
  stops the detached demo worker via the server's fenced
  `--stop-demo-worker` path, and removes its own lock. Ctrl+C / window close
  runs the same path. `-Stop` stops a running instance without starting.

Exit codes: `0` ok/ready/stopped, `1` startup/shutdown failure,
`2` port conflict, `3` already running (`-CheckOnly` only).

Useful flags: `-Port <n>`, `-NoBrowser`, `-CheckOnly`, `-Stop`,
`-WaitSeconds <n>`, `-ServerExe/-ServerArgs/-WorkDir` (dev overrides).

## Build

From the repo root (Windows, Python 3.12+, Node+pnpm):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\desktop\build.ps1
```

Reads `VERSION` (single source), pins the toolchain in-script
(`pyinstaller==6.22.3`), builds the frontend, freezes worker then server
(one-dir each; the worker ships as data inside the server bundle), smoke
tests the frozen `--version` + bundled worker path, assembles
`dist/FieldRook-<VERSION>/` + `.zip`, and writes `SHA256SUMS.txt` + `BOM.txt`
(tool versions, pip freeze, artifact hashes). No code signing (not
authorized). The build refuses to run if secret-like files (`.env`, `*.pem`,
`*.key`, `*.token`) sit in the checkout.

## Removing

Delete the install dir; then optionally remove `%LOCALAPPDATA%\FieldRook`
(DB, demo state, logs, lock). No registry, services, or admin were used.
