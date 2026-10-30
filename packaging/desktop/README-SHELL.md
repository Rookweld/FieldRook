# FieldRook shell packaging (M026 ALPHA)

Companion to `README.md` (frozen server + launcher). This file covers the
native shell half of contract section 6.

## Files

```text
packaging/desktop/
  Build-Shell.ps1   publish the WPF shell + integrate into the bundle
  README-SHELL.md   this file
```

`build.ps1` is untouched by ALPHA: the shell integrates *after* it runs.
(The lead may fold the call into one command; the two-step order stays.)

## Build order

From the repo root (Windows, .NET 10 SDK for the shell step):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\desktop\build.ps1
powershell -ExecutionPolicy Bypass -File packaging\desktop\Build-Shell.ps1
```

`Build-Shell.ps1` reads `VERSION` (single source), stamps the assembly,
publishes win-x64 single-file, and — when `dist/FieldRook-<VERSION>/`
with `server/FieldRook-Server.exe` exists — copies `FieldRook.exe`
beside `server/`, appends its hash to `SHA256SUMS.txt`, appends shell
provenance (SDK version, WebView2 SDK pin + runtime requirement, publish
mode) to `BOM.txt`, and refreshes the `.zip`. Without a prior `build.ps1`
it publishes to `dist/_work/shell-publish/` and says so (exit 0).

`-PublishMode FrameworkDependent` builds the small variant instead of
the self-contained default; the BOM records whichever was built.

## Portable layout (M026)

```text
FieldRook-<VERSION>/
  FieldRook.exe              shell (WPF + WebView2; start here)
  FieldRook.bat / FieldRook-Launcher.ps1 / README.txt   (M025 launcher, kept)
  server/FieldRook-Server.exe + server/_internal/
```

The M025 `.bat`/launcher path keeps working (browser UI); the shell is
the new default entry point (windowed UI). Removing: delete the install
dir, then optionally `%LOCALAPPDATA%\FieldRook` (DB, demo state, logs,
lock, WebView2 data). No registry, services, admin, or signing.

## Required runtimes (stated honestly)

- Self-contained shell: WebView2 Runtime only. Missing → native error
  dialog with install guidance (no crash, no silent fallback).
- Framework-dependent shell: WebView2 Runtime + .NET 10 Desktop Runtime
  x64 (per-user install suffices).
- No Python/Node on the target, no admin, localhost only (unchanged).
