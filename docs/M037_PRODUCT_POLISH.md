# M037 — Product Polish: Reports, History, Support

**Base:** M036 commit `b5e173e`
**Branch:** `m037/product-polish`
**Scope:** product UX and evidence-faithful reporting, not the diagnostic engine.

## Shipped in this development branch

### Report workflow
- Replaces raw Markdown/JSON report anchors inside Resolve with a single Case Report card.
- Uses the existing `useExport()` path: native Save As dialog in the Windows host; browser file download without the host.
- Offers an on-demand, scrollable full Markdown report preview. Report text is rendered as text, not trusted HTML.
- Offers an explicit **Copy ticket handoff** action with success/failure feedback; clipboard is never written implicitly.
- Displays administrative case filing, recorded technical verification and evidence count separately.
- Remounts the report preview after a case mutation to prevent cached previews showing pre-filing state.
- Removes the duplicate export link from the filed-case panel.

### Honest Markdown export
- Adds a short Ticket overview before the detailed, numbered audit sections.
- Explicitly marks filing as technician administrative status, not technical proof.
- Corrects the verification section to recognize recorded VERIFIED_RESOLVED resolution plans and approved actions, as well as verified executions.
- Avoids presenting the most recent unverified execution as the final verified outcome.
- Preserves the detailed evidence journal, timeline, references and technical steps after the overview.

### Launchpad becomes a technician dashboard
- When cases exist, the hero is more compact, and the repeated introduction is replaced by **Pick up where you left off**.
- Counts open cases and cases awaiting follow-up, with a direct case continuation action.
- The recent-case list can be filtered by Open, Follow-up, Handed off, or Resolved, and searched.
- Last-updated dates replace the more confusing original-created-only date.
- History report exports also use the native-aware export workflow.
- Counts refer to the fetched recent-case dataset, not an unbounded database-wide total.

### Settings and UI consistency
- Adds **Support & troubleshooting** with an explicit safe support summary copy action: version, service, platform, model mode and diagnostics capability, never keys, notes, evidence, paths or raw logs.
- Moves standalone service diagnostics into an **Advanced tools** disclosure.
- Centralizes case-filing labels and technical-verification labels in `frontend/src/casePresentation.ts` so different UI surfaces do not disagree.

## Light verification performed
- `frontend/npm run build`: TypeScript and Vite production build PASS.
- Backend report exporter Python syntax compiled.
- Isolated report smoke: technician-reported resolved remains unverified until a separate recorded verification plan exists — PASS.
- `git diff --check`: no whitespace errors.
- No full backend suite, Playwright test sweep, real-machine visual acceptance or packaged release executed.

## Boundaries and next product gates
- Does not modify authorization, evidence, action execution or diagnostic algorithms.
- Does not claim packaged Windows export/clipboard visual UX is verified.
- Full external support readiness still requires installer lifecycle, privacy-review of exports, clean-machine trials, accessibility and final regression pass.
- Published rc.2 remains untouched. No push or deployment.
