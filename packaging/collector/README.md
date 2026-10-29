# FieldRook Collector exe (M025 ALPHA)

Portable Windows collector: `FieldRook-Collector.exe`, frozen from the
stdlib-only [`collector/`](../../collector/) package with PyInstaller
**one-dir**. Same `collect | validate` CLI, same exit codes, same consent
double-gate as `python -m collector`. Packages it produces are
byte-compatible with the existing verify/import path (ZIP format FROZEN per
`docs/FORGE_CONTRACTS.md` §2) — no new format, no auto-transmit, no
services, no admin required.

## Build

Prerequisites: Windows, a host Python 3.13/3.14 (build machine only —
target machines need nothing), network for the one-time pinned
`pip install`.

```powershell
powershell -ExecutionPolicy Bypass -File packaging/collector/Build-Collector.ps1
```

What the script does:

1. Creates an isolated venv in `packaging/collector/.build/venv`
   (override: `-PythonExe`, `-BuildDir`, or `-SkipVenv` to reuse PATH).
2. Installs the pinned freezer from
   [`requirements-build.txt`](requirements-build.txt)
   (`PyInstaller==6.22.3`; refusal on version mismatch).
3. Freezes [`FieldRook-Collector.spec`](FieldRook-Collector.spec)
   (one-dir, `console=True`, UPX off, `PYTHONHASHSEED=0`) into
   `dist/collector/FieldRook-Collector/` (override: `-OutputRoot`).
4. Smoke-tests the exe: `--help` (exit 0) and `validate` of the committed
   `collector/samples/sample_basic.zip` (exit 0).
5. Writes `README.txt`, `SHA256SUMS.txt`, and `BUILD-BOM.txt` (tool +
   version + artifact hashes) into the portable dir.

## Portable dist-dir layout

`dist/collector/FieldRook-Collector/` is xcopy-portable (USB OK): the exe
plus its `_internal/` runtime. It writes nothing beside it — only the
`.zip` path you pass to `collect` and temp files (deleted after use).

```text
dist/collector/FieldRook-Collector/
  FieldRook-Collector.exe   # console exe; run from a console so the
                            # consent screen is visible
  _internal/                # frozen runtime (python DLL, stdlib, collector.*)
  README.txt                # technician usage (from PORTABLE-README.txt)
  SHA256SUMS.txt            # "<sha256>  <relative/path>" for every file above
  BUILD-BOM.txt             # build record: toolchain versions, git commit,
                            # exe hash, signing statement
```

Verify after copying:

```powershell
Get-FileHash .\FieldRook-Collector.exe -Algorithm SHA256  # compare to BUILD-BOM.txt
```

## CLI parity

The exe forwards 1:1 to `collector.__main__.main` (see
[`collector_entry.py`](collector_entry.py)):

| command | behavior |
|---|---|
| `--help` / `-h` | usage text, exit 0 (no args: usage, exit 2) |
| `collect --out P.zip --yes ...` | consent screen, then collection; exit 2 without `--yes` |
| `validate P.zip` | `VALID: ...` exit 0, or `INVALID: ...` exit 1 |
| unknown command | error, exit 2 |

`backend/tests/test_collector_frozen.py` asserts this parity (including
byte-identical `--help` vs `python -m collector`) plus an
exe-produce → existing-verify roundtrip. It skips gracefully when the exe
was not built (`FIELDROOK_COLLECTOR_EXE` overrides the default path).

## Frozen-compat notes

- **Hidden imports** live in the spec: every `collector.*` module is
  listed, covering the function-local imports in `archive.py`
  (`hashverify`, `manifest`). No behavior change to `collector/*`.
- **Child-console flash**: `_run_powershell` in
  `collector/collect_windows.py` passes `CREATE_NO_WINDOW` on Windows.
  Under a console (normal use, frozen or not) the child already inherits
  the parent console, so stdout/stderr/exit codes are unchanged; the flag
  only suppresses a flash if the collector ever runs windowed.
- **No `sys._MEIPASS` handling needed**: the collector ships no data
  files and resolves nothing relative to `__file__`; PowerShell is found
  via `shutil.which` (PATH works frozen) and temp/output go through
  `tempfile`, all freezer-compatible.

## Reproducibility & signing

Same host Python + pinned PyInstaller + this spec reproduces the same
file set; `PYTHONHASHSEED=0` and UPX-off keep the output deterministic in
practice (embedded absolute paths may still differ across machines — the
BOM records the authoritative hashes of each build). The exe is **not
code-signed** (not authorized for M025); expect a SmartScreen prompt on
first run from a download.
