# FieldRook 0.5.0 — Discord showcase (ready after repository update)

## Main announcement

**FieldRook 0.5.0 — from a browser-based troubleshooting prototype to a native Windows diagnostic workstation** 🐦‍⬛

I build IT tools under **ROOKWELD**, and this is my solo project for the Meta Global AI Developer Hackathon.

FieldRook helps Windows technicians investigate unfamiliar problems without treating AI guesses as facts. It gathers bounded, read-only diagnostics, accepts integrity-checked Collector packages from affected computers, links findings to evidence, and keeps the technician in control of proposed actions and verification.

This release is a big one:
- **A real Windows app:** a WPF + WebView2 shell around the existing React/FastAPI investigation engine. Own window, native dialogs, drag-and-drop import, persistent cases, and managed backend lifecycle — not just a browser tab.
- **SIGNALFORGE:** a completely rebuilt retro-futuristic interface with coral/plum colors, subtle circuit-trace motion, a living signal motif, and Alive / Quiet / Off modes.
- **Evidence-first workflow:** separate observed facts, hypotheses, and technician actions; never recheck a remotely collected measurement against the wrong PC.
- **Portable Collector:** an independent Windows executable for authorized, read-only evidence capture and offline package transfer.

**Validation:** 47/47 Playwright E2E, 66/66 .NET shell tests, 37/37 diagnostic gauntlet, plus 684 backend tests passed with four environment-dependent skips in the recorded M026 gate. Native-window smoke and a packaged import/export/restart journey were also exercised.

**Repo:** https://github.com/Rookweld/FieldRook
**App screenshots & UI capture:** in the updated README once published.

The next experiment is **The Field Kit** — a context-aware instrument dock with tools like Network Lab and Evidence Lens. That expansion is a **prototype**, not a shipped feature yet.

Would love feedback from other builders, particularly on the diagnostic UX and what you would want in a technician's toolbox.

*ROOKWELD — FORGE. BUILD. IMAGINE.*

## Technical follow-up (reply to your announcement)

A detail I found surprisingly tricky: the **visual redesign temporarily broke investigation continuity**. Moving the React engine between layout branches caused a remount and orphaned the active intake; our E2E suite caught it. A stable React key across the layout transition fixed the composition issue. This is exactly why UI polish still needs end-to-end validation.

Architecture: WPF/WebView2 native host → production React UI → loopback FastAPI backend. The host owns and fences its child processes; native bridge operations are typed and allowlisted, and Collector archives are validated before evidence adoption. Model outputs are never authority to execute arbitrary shell commands.

The animated circuits and signal trace are **ambient design**, not pretend hardware telemetry. Motion supports Alive / Quiet / Off and reduced-motion settings.

The UI journey is a Chromium capture of the same production React build, while the screenshots show the native application. I am keeping that distinction explicit.

## Recommended attachments (in order)

1. `docs/assets/m026/launchpad-native.png` — real app launchpad.
2. `docs/assets/m026/workbench-case.png` — active investigation and next step.
3. `docs/assets/m026/evidence.png` — evidence and provenance.
4. `docs/assets/m026/import.png` — Collector import.
5. `docs/assets/m026/demo-journey.webm` — production UI journey (Chromium capture, not WPF recording).

Do not attach the Field Kit Lab concept as if it were a shipping capability. If teasing it, label it **design prototype / work in progress**.
