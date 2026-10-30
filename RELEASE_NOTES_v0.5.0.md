# FieldRook v0.5.0 — Release Notes (draft)

## Highlights

**A native Windows experience.** FieldRook now runs in a dedicated WPF + WebView2 window, with the packaged Python/FastAPI backend managed locally. The app supports window controls, a single-instance guard, native file dialogs, drag-and-drop evidence imports, and controlled shutdown.

**SIGNALFORGE.** The retro-futuristic redesign replaces the older dashboard look with plum and coral surfaces, technical instruments, and a restrained motion system offering Alive, Quiet, Off, and reduced-motion support.

**Evidence-driven investigations remain intact.** The new UI is connected to the real investigation lifecycle, case history, Collector import, hypotheses, technician observations, and export. Target-isolation protections and consent boundaries remain in effect.

**Portable Collector.** A separate Windows executable captures authorized read-only diagnostics, creates a versioned, hash-verified package, and lets a technician transfer measurements for validated import.

## Validation reported for M026

- Backend: 684 passed, 4 environment-dependent skips.
- Playwright E2E: 47/47 passed.
- .NET shell: 66/66 passed.
- Diagnostic gauntlet: 37/37 passed.
- Native frozen-app smoke and actual case import/export/restart persistence checked.
- Security: 11/11 live probes, plus secret scanning.

These are local release-candidate results, not a claim of universal machine compatibility.

## Known limitations

- Windows portable build is unsigned; SmartScreen and AV reputation acceptance have not been validated across vendors.
- WebView2 Runtime is required on target PCs; missing-runtime behavior was reviewed but not live-tested.
- Second-PC full field trials, upgrades, selected elevated Collector capabilities, and varied hardware remain unvalidated.
- Local AI inference speed is hardware-dependent, especially CPU-only.
- Field Kit Expansion is an interactive design prototype, **not included** as six functional tool modules in v0.5.0.

## Media note

`docs/assets/m026/demo-journey.webm` records the production React UI in Chromium; it is not a native WPF window recording. Native screenshots are supplied alongside it.

## Installation

Distribute the entire `FieldRook-0.5.0` directory together, not only `FieldRook.exe`. The `FieldRook-0.5.0.zip` package should be uploaded to GitHub Releases only after verifying its hash and BOM against the release commit. Do not commit the binary ZIP into the source repository.

## Source

Source changes on `m026/desktop-rebirth`; final local checkpoint `e185200` before any documentation-only changes. See `docs/M026_DELIVERY.md` for the validation and artifact manifest.
