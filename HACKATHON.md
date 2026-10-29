# FieldRook -- Meta Global AI Developer Hackathon 2026

Indie Developer track - "Build for Your World" - October 26 - November 4, 2026
(US Eastern Time). Project by ROOKWELD (Pontus Lindh).

FieldRook is an evidence-driven AI troubleshooting assistant for IT
technicians: **Diagnose. Verify. Resolve.** Its defining principle is to
distinguish what the AI believes from what the system can actually prove
(OBSERVED / INFERRED / UNVERIFIED).

## Development during the event

All commits below were authored during the hackathon window (original Git
timestamps preserved; history has not been rewritten):

| Commit | Date | Subject |
| ------ | ---- | ------- |
| `7c99644` | 2026-10-26 | Milestone 001: first diagnosis vertical slice |
| `35aebed` | 2026-10-26 | Map PowerShell status enums to names; allow pnpm esbuild script |
| `10c8f8f` | 2026-10-26 | Recommend pnpm in frontend quickstart |
| `9a37ee9` | 2026-10-26 | Map ServiceType flags to names |
| `48551e4` | 2026-10-26 | feat(fieldrook): complete milestone 002 eyes of the raven |
| `3f8196f` | 2026-10-26 | feat(fieldrook): add read-only scheduled-tasks diagnostics (case 001) |
| `f87aecb` | 2026-10-27 | feat(fieldrook): complete milestone 003 controlled fix |
| `ca4f4c2` | 2026-10-27 | chore(fieldrook): prepare open-source hackathon release |
| `0e5da37` | 2026-10-27 | feat(fieldrook): milestone 004 field demonstration |
| `cc9907d` | 2026-10-27 | fix(ci): declare frontend pnpm workspace |
| `cf6f3d4` | 2026-10-27 | fix(ci): declare pnpm frontend workspace |
| `459583c` | 2026-10-27 | docs(fieldrook): showcase real workstation screenshots |
| `b9fd710` | 2026-10-27 | feat(fieldrook): milestone 005 proof of value |
| `814c03b` | 2026-10-27 | feat(fieldrook): milestone 006 the field technician |
| `d29b41a` | 2026-10-27 | feat(fieldrook): milestone 010 reality check |
| `b4d481e` | 2026-10-27 | feat(fieldrook): milestone 011 technician pilot |
| `2815771` | 2026-10-27 | feat(fieldrook): milestone 012 focused workstation |
| `c92ba2e` | 2026-10-27 | feat(fieldrook): milestone 013 the living forge |
| `252677e` | 2026-10-27 | feat(fieldrook): milestone 014 cinematic atmosphere |
| `1261815` | 2026-10-28 | feat(fieldrook): milestone 015 living investigation |
| `acb334c` | 2026-10-28 | feat(fieldrook): milestone 016 the real technician |
| `f8636ca` | 2026-10-28 | feat(fieldrook): milestone 017 lightweight local intelligence |
| `bcb80ef` | 2026-10-28 | feat(fieldrook): milestone 018 unknown problem challenge |
| `9284952` | 2026-10-28 | feat(fieldrook): milestone 019 technician loop |
| `0610d16` | 2026-10-28 | feat(fieldrook): milestone 020 collector foundation (forge checkpoint) |
| `69238e1` | 2026-10-28 | feat(fieldrook): milestone 021 diagnostic expansion (forge checkpoint) |
| `dc22992` | 2026-10-28 | feat(fieldrook): milestone 022 knowledge-backed investigation (forge checkpoint) |
| `17b632c` | 2026-10-28 | feat(fieldrook): milestone 023 unified workstation (forge checkpoint) |
| `f6a52cf` | 2026-10-28 | feat(fieldrook): milestone 024 validation and distribution (forge checkpoint) |

Milestone 001 (first diagnosis slice), Milestone 002 (natural-language
intake, screenshot understanding, tool-calling investigations, follow-ups),
the real-world scheduled-task diagnostic case, Milestone 003 (registry-only
corrective actions, single-use human approval, demo-worker recovery,
independent verification, SQLite persistence, Markdown/JSON export, Windows
error-code interpretation), Milestone 004 (three-stage workstation,
reproducible demo scenarios, Playwright e2e, demo ops scripts, CI, demo
package), Milestone 005 (split approve/execute UX with expiry recovery,
16-case diagnostic gauntlet with live-model evals, phantom safe-guidance,
static recorded jury demo), Milestone 006 (application-crash and
process/service/DNS diagnostics, symptom triage planner, incident overview,
evidence-linked runbook steps, technician notes, 34-case gauntlet, Windows
field testing), and Milestone 007 (on-demand evidence reverification with
historical preservation, contradiction detection, targeted re-checks,
investigation progress UI, four field scenarios, 39-case gauntlet), and
Milestone 008 (resolution plans with measurable criteria, Confirm Fix
baseline/verify workflow, VERIFIED_RESOLVED/NOT_RESOLVED/INCONCLUSIVE
outcomes, resolution workspace, eight verification scenarios, 43-case
gauntlet), and Milestone 009 (verified resolution library, deterministic
similar-incident matching, Worked Before panel, on-demand regression
rechecks, redacted local knowledge management, 47-case gauntlet), and
Milestone 010 (full product audit with ten fixed findings, five measured
field trials, plan-aware header and clickable stage stepper,
historical-evidence collapsing, plan timeline rounds, badge tooltips,
debounced search, visible keyboard focus, before/after screenshots,
47-case gauntlet re-measured), and Milestone 011 (live technician
pilot on genuine Windows data, four pilot defects fixed, first-run
guide and acceptance checklist, 47-case gauntlet re-measured), and Milestone 012 (focused-workstation
UX overhaul: Findings / Evidence / Resolve views, three-second result
header, readable evidence summaries, summary-first evidence preview,
honest pending states, error boundary, token design system, 21-test
Playwright suite), Milestones 013-019, and FORGE checkpoints
M020-M024 were all designed and implemented during the event (see the table; M024.1 hardening is recorded in the commit history and `docs/FORGE_LEDGER.md`).

## Meta Muse Spark integration

Reasoning, tool calling, and screenshot vision run on `muse-spark-1.3` via
the Meta Model API (`MODEL_API_KEY`, OpenAI-compatible chat shape). The model
receives structured observations and returns evidence-cited assessments; it can
request named read-only diagnostic tools and propose (never execute) registered
corrective actions. Without a key, FieldRook falls back to clearly labeled
deterministic simulated analysis.

## Pre-existing components

None. The repository was created during the hackathon; every source file,
fixture, and document above originates from the event period. Third-party
packages (see `backend/requirements.txt`, `frontend/package.json`) and the
Apache-2.0 license text are the only external artifacts.
