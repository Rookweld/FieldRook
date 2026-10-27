# FieldRook Manual Acceptance Checklist

For the human technician: work through these on a real Windows machine
with live diagnostics and (ideally) a `MODEL_API_KEY`. Each item states
what to do and what counts as passing. All items passed during the M011
pilot on 2026-10-27 except where noted.

## A. Startup and honesty signaling

- [ ] **A1.** Backend starts on `127.0.0.1:8000`, frontend on
  `localhost:5173`, no errors in either terminal.
- [ ] **A2.** Header badges match reality: `LIVE MODEL` only with a key
  set, `SIMULATED MODEL` without; `LIVE DIAGNOSTICS` on Windows with
  PowerShell. Hovering a badge explains it.
- [ ] **A3.** With no key, an investigation warns that analysis is
  simulated and names the limitation honestly.

## B. Live investigations (read-only)

- [ ] **B1. Service.** Service lookup for `wuauserv` returns real status
  (`Stopped`/`Manual` on a default machine) with
  `powershell:Get-Service` provenance and a `LIVE` evidence label.
- [ ] **B2. Application.** "Has Excel crashed in the last day?" returns a
  measured answer (matches or an honest zero) with event IDs and
  timestamps, every fact citing an `ev-N` chip.
- [ ] **B3. Network.** A DNS question runs `get_dns_config` /
  `test_dns_resolution` and reports functional or broken from
  measurement, not assumption.
- [ ] **B4. Scheduled task.** A task question collects real scheduled
  tasks; a nonexistent task name is reported as not found, never
  invented.
- [ ] **B5. Ambiguous.** A vague symptom ("slow this morning") yields an
  honest low-confidence assessment with explicit uncertainties and
  missing evidence — not a confident guess.
- [ ] **B6. Warnings visible.** Any truncated evidence card shows its
  "was truncated" warning above the JSON; failed collections show the
  error and the investigation continues.

## C. Investigation workflow

- [ ] **C1. Follow-up.** A follow-up question continues the same
  investigation as a new timeline round without losing history.
- [ ] **C2. Re-check.** Re-checking an evidence card preserves the
  historical item, labels the new reading, and reports a verdict
  (`CHANGED` / `UNCHANGED` / `UNAVAILABLE`).
- [ ] **C3. Notes.** A technician note saves and survives history reopen.
- [ ] **C4. History.** Closing and reopening an investigation from
  History (including after a backend restart) restores evidence,
  timeline, plans, and notes intact.

## D. Resolution and verification

- [ ] **D1. Plan.** A resolution plan requires measurable criteria
  (tool + value path + comparison); unverifiable claims are rejected.
- [ ] **D2. Baseline.** Capturing the pre-fix baseline records real
  measurements with timestamps.
- [ ] **D3. Honest outcomes.** Confirm Fix without a real recovery
  reports `NOT_RESOLVED` or `INCONCLUSIVE` — never resolved on a
  button click. (Pilot: demo-worker recovery measured
  `VERIFIED_RESOLVED` with before/after states.)
- [ ] **D4. Approval boundary.** The demo-worker action requires
  propose → approve → single-use token → execute; no other
  system-changing action exists in the UI.

## E. Memory and export

- [ ] **E1. Remember.** Saving an investigation to knowledge records a
  redacted entry (no usernames, command lines, or credentials in
  signatures).
- [ ] **E2. Match.** A repeat incident suggests the historical entry
  with inspectable signals and explicit differences — as a reference,
  never as proof, and never auto-executed.
- [ ] **E3. Export.** Markdown export of an investigation contains the
  summary, timeline, evidence, and outcome, and opens correctly.

## F. Performance and reliability

- [ ] **F1.** Live investigations complete in under ~60 seconds each
  (pilot measured 11–42s for 1–7 tool calls).
- [ ] **F2.** No console errors, no failed API requests, no stuck
  loading states during the walk above.
- [ ] **F3.** Library search does not send a request per keystroke.

## Sign-off

Accepted by: ____________________  Date: __________

Notes / deviations:
