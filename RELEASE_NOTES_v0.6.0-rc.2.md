# FieldRook v0.6.0-rc.2 — Release Candidate Notes

**Status: published GitHub pre-release (November 17, 2026).**
This candidate incorporates M030 local provider probe correctness, cancellation,
API-style honesty, and loopback hardening after the published v0.6.0-rc.1.

## Changes since rc.1

- A technician's explicit local-model connection test refreshes both Ollama
  detection and server-advertised model capabilities, even after a cached
  negative result. Background checks continue using a bounded cache.
- Cancellation before or during slow local `/api/tags` and `/api/show`
  probes stops the FieldRook round promptly, retains existing evidence, and
  does not invent an assessment.
- Provider listing is cache-only, with `unresolved` before a probe rather
  than a guessed API style.
- Direct local model probes enforce a loopback-only destination before
  constructing HTTP clients. Local calls do not forward cloud API tokens.
- Backend release dependencies are pinned to the versions verified with
  Python 3.12; the packaging script rejects mismatched interpreters and
  uncommitted source trees.

## Verifications preceding packaging

- 734 backend tests passed, 4 skipped (Python 3.12.10 isolated venv).
- 98 Playwright end-to-end tests passed using the isolated FastAPI backend.
- 66 native/.NET unit tests passed; WPF Release build completed without
  warnings or errors.
- Frontend TypeScript check and Vite production build passed.
- Real Ollama loopback request and a basic `qwen3:8b` `OK` chat passed.

These development checks do not substitute for frozen-package smoke tests.
Release hashes and exact build provenance must come from the packaging BOM.

## Known limitations

- The Meta cloud provider is not verified by this release run; tests use
  simulated/fixture providers unless otherwise stated.
- Optional Field Kit modules (Process Watch, Event Decoder, Command Deck,
  Field Notes) remain design concepts, not functioning shipped features.
- The executable is unsigned; Windows SmartScreen may warn.
- WebView2 Runtime is required on Windows even for the self-contained shell.
- Not yet certified on a second machine, no-WebView2 installations, or
  upgrade-over-existing-install scenarios.
- A high-severity `picomatch` advisory affects Vite tooling (development
  dependency only, as observed during M030 review). Production dependency
  audit found no known advisories. Track upstream before later releases.
- Deferred D4 redundant-probe coalescing and D6 capability/vision status
  flicker are not resolved by M030.

## Download and provenance

The published [GitHub pre-release](https://github.com/Rookweld/FieldRook/releases/tag/v0.6.0-rc.2)
contains `FieldRook-0.6.0-rc.2.zip`, `SHA256SUMS.txt`, `BOM.txt`, and
`RELEASE_VALIDATION.md`. The frozen server and launcher lifecycle were tested
from the extracted ZIP, and GitHub asset SHA-256 hashes were verified against
the locally built originals. The earlier rc.1 release remains available.
