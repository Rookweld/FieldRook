# M036 — Technician Case Filing, Handoff & Reopen

Branch: `m036/case-lifecycle`
Base: M035 commit `9edc8df`

## Operator workflow
1. Start or reopen an investigation.
2. Complete diagnostics / technical verification when possible.
3. In **Resolve**, use **Case status**: resolved (technician-reported), waiting for follow-up or handed off.
4. A filing note is required; the chosen disposition and filing timestamp are saved with the case.
5. The case banner and recent history show the current administrative status. Filed cases can be reopened.
6. The Markdown/JSON report includes the administrative filing, timestamp and note.

## What counts as proof
- **Case disposition is not an evidence verdict.** In particular, "resolved" is the technician's status and does not promote a non-verified fix to "VERIFIED_RESOLVED".
- Actual measured verification, approval and action records remain separate and unchanged.
- The UI warns when someone files a case as resolved without recorded verification.
- Closed-case activities aren't automatically forbidden at the API level: the disposition is an administrative filing, not an authorization or mutation lock.

## Compatibility and persistence
- Uses existing SQLite `assist.doc_json` record for disposition, closed_at and closure_note; **no schema migration**.
- Existing/legacy investigations default to `open`.
- Reopening clears the current disposition and closure fields, but the prior full filing note remains in technician notes and activity history.
- Save and list routes load the same source of truth; case history remains usable across backend restarts.
- New endpoint: `POST /api/investigations/{investigation_id}/disposition` with `{disposition, note}`.
- Only `open`, `resolved`, `needs_followup` and `handed_off` are valid; non-open filings require an actual note.
- New fields in response/summary are backward-compatible defaults.

## Product UI
- An immediate filing/reopen panel in Resolve, before advanced resolution internals.
- Measurement and controlled actions live in a labeled expandable section.
- Filed-case banner above the workbench with a direct shortcut to Resolve.
- Searchable case history includes the filing status and displays friendly status instead of diagnostic-round "complete".

## Verification and outstanding work
- TypeScript production build passed.
- Python files compiled.
- One isolated temporary-SQLite smoke scenario verified **create → file → persist → list → Markdown export → reopen**, including retention of the original filing note. No operator database was touched.
- No full regression suite, E2E visual walkthrough, production installer or real user acceptance performed.
- Potential subsequent polish: single unified Report view with printed/PDF export, reopen-from-history shortcut, and a distinct UI cue for active but stale cases.
- No merge, push or release performed in this branch.
