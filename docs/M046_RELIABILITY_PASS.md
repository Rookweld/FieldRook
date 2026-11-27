# M046 — The Reliability Pass (first verified tranche)

**Base:** `v0.6.0-rc.6` (commit `7be174b`)
**Branch:** `m046/reliability-pass`
**Scope:** Reconcile legacy UI regressions with the simplified M045 interface, without adding operator-facing clutter or changing the released rc.6 artifacts.

## Verified

- Backend: **925 passed, 4 skipped, 2 warnings** in 215.63 seconds.
- Frontend: TypeScript check and Vite production build **PASS**.
- Corrected approval/rejection and evidence preview flows: **3/3 PASS**.
- Case assessment, resolution plan, Collector consent, and extended workbench focused recheck: **4/4 PASS**.
- Field Kit dock reworked to test shipped, ready instruments, collapsed defaults, evidence selection continuity, keyboard focus, pin persistence, obsolete stored preferences, and narrow overlay: **8/8 PASS**.
- Evidence Lens and status/provider endpoint representative checks: **4/4 PASS**, with the fifth Network Lab provenance test **PASS** on its targeted recheck after updating the hidden-badge assertion.

The focused UI totals above are separate runs, not one whole-suite green result.

## Fixes to the test contract

1. Use actual expandable **Evidence & assessment**, **Technical verification & approved actions**, and **Additional investigation tools** sections rather than demanding that everything be open by default.
2. Respect intentionally collapsed and mobile-hidden Field Kit states; test explicit opening, focus, persistence, and evidence selection.
3. Stop asserting for unfinished instruments that the product deliberately filters from its public dock. Test that legacy stored IDs cannot surface them.
4. Use the selected dynamically allocated test-server port instead of hardcoding port 8123 in five E2E specs; Windows can reserve port 8123.
5. Assert the visible fixture/provenance indicator in the focused workbench, instead of a badge inside a collapsed assessment.
6. Keep action-approval safety checks (no execution on rejection; deliberate approval before execution), evidential provenance checks, and report/diagnostic UI contracts.

## Known limits / follow-up

- A previous broad **117-case** E2E run using the legacy/dirty worktree showed many failures and was interrupted. It cannot be called a clean full-suite regression result.
- The remaining, older E2E specs should be triaged against the shipped rc.6 UI, with real defects fixed in product code and obsolete expectations updated rather than deleting checks for genuine capabilities.
- This tranche changes **tests and test harness only**. It is not a new installer build, code signing, a functional feature release, or validation on an additional clean user PC.
- The public rc.5 and draft rc.6 binaries remain unchanged.

## Exit criteria for the remainder of M046

1. Full Playwright run against a clean branch with no unresolved unexplained failures.
2. Repeat backend tests after any product-code correction.
3. Verify any user-reported production issues with a reproducer and regression.
4. Create a new test installer only when substantive application code changes warrant it.
