# FieldRook v0.6.0-rc.1 — Release Notes (pre-release candidate)

**Status: pre-release, development build. Not stable. Not yet published.**
This candidate includes the functional M028/M029 Field Kit, which is NOT in the v0.5.0 binaries.

## What is new since v0.5.0

- **Field Kit dock** — modular right-hand instrument framework (pins, keyboard access, narrow-overlay support).
- **Evidence Lens** — deterministic before/after record compare over persisted evidence, contradiction citations, export linkage.
- **Network Lab** — read-only networking instrument (adapters, addresses, DNS config, resolution test) with consented re-checks and a remote-target guard.
- **Network Lab success-notice fix** — the re-check confirmation survives lab updates (no remount clearing).
- **Reproducible demo scenario** — "The FieldRook demo worker is down", documented step-by-step in `docs/demo/M028_THREE_MINUTE_DEMO.md`.

Remaining Field Kit modules (Process Watch, Event Decoder, Command Deck, Field Notes) are still design-prototype concepts, not shipped features.

## Provider and demo honesty

- Runtime model in the packaged demo is the deterministic simulated provider (`fieldrook-simulated-001`), badged SIMULATED MODEL / FIXTURES ONLY in-app.
- **Meta provider runtime is NOT verified in this build** (no API key at build/test time). Do not claim live hosted inference from this package. See `docs/demo/M029_META_PROOF_STATUS.md`.
- Demo readings are local fixtures; no live-cloud or operator data is bundled or contacted.

## Requirements and limitations

- Windows 10/11 x64. **WebView2 Runtime required** (evergreen; the shell shows install guidance when missing). No .NET runtime needed (self-contained shell); no Python/Node on the target.
- Binaries are **unsigned** — expect a possible Windows SmartScreen warning. Verify SHA-256 checksums before running.
- Localhost-only server bind; per-user data under `%LOCALAPPDATA%\FieldRook`; single-instance guard.
- Not certified: second-machine trials, antivirus-vendor reputation, no-WebView2 machines, upgrade-over-existing installs. See README "Validation and known limits".

## Package contents

- `FieldRook-0.6.0-rc.1/` — portable app dir: run `FieldRook.exe`, keep the folder together.
- `FieldRook-0.6.0-rc.1.zip` — shippable archive (verify hash, then unzip).
- `SHA256SUMS.txt` — hashes of the archive and executables.
- `BOM.txt` — build provenance: exact source commit, toolchain pins, artifact hashes.

Distribute the entire directory together, not only `FieldRook.exe`. Do not commit the binary ZIP into the source repository.

## Verification (build-time gates)

- Backend pytest, frontend tsc + Vite build, .NET suite, full Playwright E2E, frozen `--version` identity check, headless lifecycle smoke, and the packaged fixture scenario all pass on the release-commit build. Exact numbers and hashes are in the build BOM and the versioned readiness report.
