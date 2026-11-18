# M034 — Product Experience & Decluttering

**Branch:** `m034/product-experience`
**Base:** M033-G `44d2600`
**Intent:** Stop growing experimental chrome. Make the normal technician flow obvious while retaining the technical capabilities behind progressive disclosure.

## Product principles
1. **One case, one next action.** The next meaningful check is above diagnostic detail.
2. **Reported is not measured.** The UI keeps model/fixture/live states explicit.
3. **Real controls only.** No pretend quick capture or unfinished instruments in primary UI.
4. **Details on demand.** Nothing is deleted from the case data or analysis engine.
5. **Accessible recovery.** Connection status refreshes automatically; no full-page reload needed when the backend starts late.

## Changes
- Launchpad: actionable three-stage onboarding, searchable recent cases, reduced duplicated runtime status.
- New-case Workbench: immediately exposes real intake; no second full-height hero and no idle decorative signal scope.
- Active case: compact context header, single main next-step action, optional folded case context/activity, real note/evidence/import shortcuts.
- Existing React investigation engine remains keyed/stable while intake becomes an active case.
- Guide shortcut now selects the real Guide tab; note shortcut selects Findings before focusing the real persistent notes input; import shortcut opens the correct disclosure before focusing the file input.
- Findings: keep the primary overview visible; detailed diagnosis, history and auxiliary tools remain available inside disclosures.
- Field Kit: compact by default, remembers the operator's preferred visibility, and lists only implemented instruments. Placeholder registrations remain in source for later development.
- Shell: removes stale M026/Signalforge release labels and repeated status badges. Backend version remains in footer and Settings.
- First-run guidance only appears on the Launchpad instead of following every active investigation.
- Service status retries every 15 seconds without overlapping requests; losing connection clears stale online status.
- Case-history fetching is no longer duplicated at launch.

## Deliberately unchanged
- Backend diagnostic algorithms, hypotheses, evidence journal, action consent, execution policies and persistence.
- M033-G and published v0.6.0-rc.2; no release deployment or auto-update changes.
- Core Guided, Findings, Evidence and Resolve views. Their detailed tools are still accessible on demand.

## Quality and deferred verification
- TypeScript production build (`npm run build`) is a light sanity check, not product acceptance.
- Full backend and Playwright regression suites are **deferred intentionally**, at the owner's request while the UI is being simplified.
- Existing E2E tests assume expanded dock and always-visible auxiliary panels and will require expectation updates to reflect the new product defaults.
- A real-world visual and usability walkthrough on Fury is still required before declaring this build ready for external users.

## Follow-up priorities
1. **Product flow:** unify operator notes and follow-ups, clear case close/reopen affordances, avoid duplicate action surfaces.
2. **Installer & lifecycle:** verified clean install, upgrade and uninstall; backend boot/reconnect, portable logging and crash recovery.
3. **Privacy & permissions:** review bundled defaults, cloud consent UX, evidence retention and export redaction.
4. **Supportability:** in-app diagnostics, version details, shareable safe support bundle and actionable error states.
5. **Final acceptance:** real Windows machines, local/cloud/fixture cases, accessibility, offline handling and full regression gate.

M034 is a focused product UI iteration, **not** a claim that FieldRook is launch-ready.
