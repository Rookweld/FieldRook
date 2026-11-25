# M042 — First Impression & Investigation UX Polish

Date: 2026-11-25 (Europe/Stockholm)
Branch: m042/first-impression-ux, based on M041 commit 943a754
Release impact: None. Published v0.6.0-rc.4 remains unchanged.

## Motivation

A real browser recording replaying the historical, technician-led Fury Bridge incident showed several presentation and navigation defects:

1. The outer badge described the globally configured *default* simulated provider, even when an investigation explicitly ran with local Qwen3 4B (analysis_mode=live). The badge could misrepresent an actual case.
2. The full free-form problem was rendered as a huge uppercase heading, pushing useful controls out of view.
3. The workbench could remain scrolled near the composer after a successful follow-up or initial investigation.
4. A long next step could cause the main CTA to clip at the bottom of the panel.
5. Narrow-screen document scrolling could hide the app's topbar even if the internal workbench was scrolled to its top.

## Implemented

### Source-of-truth analysis badges

The header and footer now use the *active investigation's* model, analysis mode, fixture flag and evidence count. In the absence of a case, they explicitly label the backend's DEFAULT. A saved local-model case displays Case: Local AI even if the default is Simulation. Backend unavailable is labelled unavailable. No saved case status is misrepresented as proof that a model is currently connected.

### Compact problem title, complete original preserved

The first meaningful sentence (or a truncated word-boundary excerpt) is the headline. Complete original technician text is always preserved in the server case and can be expanded with Read the full problem report. The case metadata now says the actual number of evidence records (including zero) instead of generically claiming Collected data; fixture evidence is labelled.

### Navigation and card integrity

A successful initial analysis or follow-up moves both inner workbench and outer window to the updated case, using reduced-motion preference. Errors retain the previous scroll position. Long suggested steps no longer shrink the entire step panel so far that the OPEN GUIDE button clips.

### Portable E2E test server

frontend/playwright.config.ts accepts FIELDROOK_E2E_API_PORT as an environment override (legacy default remains 8123). Fury's actual excluded TCP ranges 8019–8118 and 8119–8218 covered test port 8123. Socket bind gave WinError 10013; read-only bind verification found 18223 available. E2E runs used 18223 without modifying Windows reservations.

### E2E selector maintenance

Older tests under guide.spec.ts, investigate.spec.ts, launchpad.spec.ts and technician.spec.ts expected removed headings or visible-by-default details. They now use the actual current launchpad heading, main next-step panel, and consciously expanded content within the visible Evidence/Findings views. These updates preserve meaningful assertions, not deleted coverage.

## Verification

- Production frontend TypeScript/Vite build: PASS (after source edits; last subsequent edits were test assertions only).
- New focused Playwright tests: 4/4 PASS. Verify case source-of-truth badge, complete original problem retained behind compact headline, accepted follow-up scroll positioning, narrow viewport, and bounding boxes showing the next-step CTA fully inside its card.
- Combined Chromium browser tests for M042, launchpad, guide, technician and investigate: **15/15 PASS** in 53.9 seconds, exit code 0.
- Visually inspected browser captures: frontend/test-results/m042-desktop-1600.png and frontend/test-results/m042-mobile-700.png. These are local ignored development artifacts, not marketing visuals.
- No FieldRook backend source changed; the earlier M041 925-pass backend result is historical and was not rerun here.

## Boundaries

No public release, clean-machine installer acceptance, broader full Playwright suite, external user feedback, audiovisual export or signed binary was attempted in M042. The actual initial historical incident replay with local AI is a separate development-only recording. Chromium fixture-based E2E checks are not evidence that a model autonomously resolved an incident.

## Next

Continue technician pilot recruitment on v0.6.0-rc.4, prioritizing real cases and honest failures. Build a release candidate after the next acceptance pass. Produce a polished 45–60 second product video after the final UI is tested, using a real historical case with explicit replay/technician-report attribution. Add original music, sound and transitions to the final truthful footage rather than the current first-cut screen recording.
