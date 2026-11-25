# M043 — First-Run Simplicity

Date: 2026-11-25 (Europe/Stockholm)
Branch: m043/first-run-simplicity
Base: m042/first-impression-ux, commit c2480d6
Published release: v0.6.0-rc.4 unchanged.

## Why

An independent early tester should be able to open FieldRook and investigate an authorized, reproducible Windows issue without reading a miniature product manual, learning providers/fixture internals, or assuming simulated results are live AI.

The previous first-run guide spanned six dense technical sections; its "Start diagnosing" control only dismissed the guide and did not open a case. Intake displayed optional services, screenshots and other technical choices upfront. Whether reasoning was simulated or live was primarily visible in advanced options.

## Improvements

1. Replaced six long first-run sections with a compact three-step "Bring a real Windows problem" flow: describe symptoms, choose affected computer, perform/record/verify checks. Technical documentation and provider configuration are retained inside an expandable explanation. Provider entries are labelled "configured", never "connected", because the providers API does NOT probe network reachability.
2. FirstRunGate accepts onBegin callback, and App now hands it the existing startNew action. The primary welcome CTA records the first-run completion marker, closes the guide, **navigates to Workbench** and opens a fresh case. Reopening/dismissal still works.
3. Intake presents one clear symptom text area, affected computer and one prominent Investigate button. Service name, screenshot with explicit sharing consent, and Collector package are moved behind an optional expandable section; the existing advanced provider and fixture controls remain available.
4. A concise readout appears BEFORE a case starts. It explains default simulated reasoning, active local model selection, potential remote processing of cloud contexts, and fixture-mode implications. The one-click local AI selector appears only when the backend reports a configured local endpoint; *configuration is not a successful connectivity test*. If backend status cannot be read, it is explicitly unavailable, never silently marked simulated.
5. The target selector explains that read-only diagnostics inspect THIS PC only. A different target is not probed remotely.
6. The intake was compacted so that on a 1600x900 viewport the symptom, affected PC selection, Investigate CTA and provenance summary are visible without scrolling. Narrow 700px screens have a stacked form without horizontal overflow; standard controls are keyboard-focusable and native disclosures remain usable. No added UI dependencies.

## Files

- frontend/src/forge/FirstRunPanel.tsx, FirstRunGate.tsx, FirstRun.css
- frontend/src/App.tsx
- frontend/src/components/ProblemWorkstation.tsx
- frontend/src/signalforge/intake-simplicity.css
- frontend/src/signalforge/views/Workbench.tsx
- frontend/tests/e2e/m043-first-run-simplicity.spec.ts

## Verification

- Frontend TypeScript check and Vite production build PASS following final source changes.
- M043-specific Playwright Chromium E2E (fixture server and one mocked provider-configuration contract): 7/7 PASS after final source changes. Tests cover first-run CTA and persisted marker, honest default inference, local AI configured-vs-reachable distinction, remote target no-scan statement, fixture visibility, explicit screenshot consent, configured cloud processing warning, and horizontal-overflow prevention on narrow screens.
- Combined browser regression on the branch (before the final copy-only refinements): 20/20 PASS across M043, M042, Launchpad, Guide, technician workflows and existing investigate tests.
- Screenshots visually inspected at 1600x900 and 700x950:
  - frontend/test-results/m043-welcome-1600.png
  - frontend/test-results/m043-intake-1600.png
  - frontend/test-results/m043-narrow-700.png
- Tests use a localhost isolated demo/fixture backend on FIELDROOK_E2E_API_PORT=18223 to bypass Windows's actual excluded TCP range containing default 8123. No Windows excluded ranges were edited.
- No live hosted cloud API was called by browser tests; the live-mode UI warning was validated by mocking only status metadata. This milestone does not claim independent diagnosis of a new real incident.

## Limits and next steps

- This is a source-development UX milestone; rc.4 release artifacts and the signed/unsigned Windows installer were not rebuilt or modified.
- Provider availability endpoint only confirms configuration. An explicit local connectivity test remains available under advanced Guide workflow; no model is downloaded or started automatically.
- The wider, complete Playwright suite beyond the chosen 20 browser checks and clean-machine installer acceptance have not been run in this milestone.
- Continue collecting real technician feedback from rc.4. For rc.5, bundle M040-M043 only after a clean-machine acceptance test and deployment review. Capture and soundtrack a new public demo from the tested candidate; keep incident reenactments clearly labelled as historical and technician-led.
