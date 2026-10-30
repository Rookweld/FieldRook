# FieldRook native shell (M026 ALPHA)

WPF + WebView2 host for the frozen desktop app. The shell owns the window
and the backend lifecycle; the React UI (served by the backend on
loopback) stays the only UI — there is no second interface to keep in
sync.

## Layout

```text
native-shell/
  FieldRook.slnx
  src/FieldRook.Core/      dependency-free logic (protocol + guards + paths)
    Bridge/BridgeProtocol.cs      typed allowlisted bridge, fail-closed
    Backend/InstanceGuards.cs     loopback nav guard + single-instance eval
    Infrastructure/AppPaths.cs    user-data paths, lock file, port discovery
  src/FieldRook/           WPF app (net10.0-windows, x64)
    App.xaml(.cs)          startup: args -> port -> probe -> backend -> window
    MainWindow.xaml(.cs)   WebView2 host, bridge wiring, drop, crash UX
    Backend/BackendManager.cs     spawn / health / fenced shutdown
    Backend/ProcessFence.cs       job object (no orphans) + WMI cmdline fence
    Backend/InstanceProbeRunner.cs  lock + TCP probe + identity (IO half)
    Bridge/BridgeExecutor.cs      native dialogs, version, window control
    app.manifest           asInvoker, PerMonitorV2 DPI awareness
    Assets/FieldRook.ico   app + taskbar icon
  tests/FieldRook.Bridge.Tests/   xunit contract tests (64)
```

## Decisions (contract section 1: ALPHA decides, documented)

- **Standard OS chrome**, not custom-drawn: min/max/restore/close, taskbar,
  resizing, and DPI scaling come from the platform and stay accessible.
  `windowControl` is still implemented (minimize/maximize/restore/close all
  work on standard chrome) but the UI does not need it.
- **Port**: `--port` / `FIELDROOK_PORT` is authoritative and never silently
  replaced. The default 8000 is kept when free or when a live Desktop
  answers on it (so the probe reports "already running"); a *foreign*
  listener on 8000 triggers free-port discovery instead of bricking first
  run.
- **Single instance**: M025 lock file + TCP probe + `/api/status` identity,
  decided by the same rules as `FieldRook-Launcher.ps1` (a live Desktop on
  ANY port wins; a dev server or foreign listener is a readable conflict).
  A named mutex supplements only the double-launch race window.
- **Health** = `service == fieldrook-api` AND `runtime == desktop` (M025 Z1
  rule, unchanged). `--dev-backend` / `FIELDROOK_SHELL_DEV=1` accepts
  `runtime == dev` for verification against an unfrozen server only.
- **Shutdown** kills ONLY the owned child PID after a command-line fence
  check (`FieldRook-Server.exe` in the WMI command line) plus a start-time
  fence against PID reuse, then the demo worker via the server's
  `--stop-demo-worker` path. A job object (`KILL_ON_JOB_CLOSE`) reaps the
  child even if the shell itself crashes: no orphan backend either way.
- **Publish mode**: self-contained win-x64 single file by default (see
  `packaging/desktop/Build-Shell.ps1`): zero target prerequisites except
  the WebView2 Runtime, matching the M025 "no toolchain on the target"
  philosophy. `-PublishMode FrameworkDependent` builds the small variant
  for machines with the .NET 10 Desktop Runtime.

## Bridge (contract section 2; GAMMA consumes)

Page → shell via `window.chrome.webview.postMessage({op, id, params})`;
shell answers `postMessage({id, ok, result} | {id, ok:false, error})`
where `error = {code, message}`. Allowed ops ONLY:

| op | params | result |
|---|---|---|
| `openFile` | `{title?}` | `{path}` — `.zip` picked in a native dialog |
| `saveFile` | `{fileName, contentBase64}` | `{path}` — bytes written where the native save dialog pointed |
| `getVersion` | `{}` | `{shell, server, runtime}` |
| `windowControl` | `{action: minimize\|maximize\|restore\|close}` | `{action}` |

Fail-closed: unknown ops, malformed envelopes, traversal/separator names
(`..`, `/`, `\`), reserved device names, non-allowlisted extensions, and
non-`.zip`/missing import paths are rejected with `{ok:false}` and never
executed. Error codes: `unknown_op`, `bad_envelope`, `bad_params`,
`invalid_path`, `cancelled`, `failed`.

Drag-and-drop of a single `.zip` onto the window posts
`{kind:"fieldrook:file", fileName, path}` to the page after the same
`.zip` validation. Navigation outside loopback http(s) is blocked and
logged. No `eval`, no filesystem access beyond dialog results.

## Verification

```powershell
dotnet build native-shell/FieldRook.slnx -c Release   # gate: exit 0
dotnet test native-shell/FieldRook.slnx -c Release    # gate: 64/64 green
```

`FieldRook.exe --smoke [--port N] [--dev-backend]` runs the lifecycle
headlessly (probe → spawn → health → fenced shutdown) and prints one
`SMOKE OK|FAIL|REFUSED` line; exit codes `0` ok, `1` failure, `2` port
conflict, `3` already running.

Dev overrides (verification only, never packaged):
`FIELDROOK_SERVER_EXE` + `FIELDROOK_SERVER_ARGS` (e.g. venv python +
`fieldrook-server-entry.py`), `FIELDROOK_SHELL_DEV=1`,
`FIELDROOK_DB_PATH`, `FIELDROOK_DEMO_STATE`.

## Build & packaging

```powershell
powershell -ExecutionPolicy Bypass -File packaging\desktop\build.ps1        # frozen server + UI
powershell -ExecutionPolicy Bypass -File packaging\desktop\Build-Shell.ps1  # shell + integrate
```

Produces `packaging/desktop/dist/FieldRook-<VERSION>/` =
`FieldRook.exe` beside `server/`, with `SHA256SUMS.txt` + `BOM.txt`
extended by shell provenance. See `packaging/desktop/README-SHELL.md`.
