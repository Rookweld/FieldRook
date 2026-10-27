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

Milestone 001 (first diagnosis slice), Milestone 002 (natural-language
intake, screenshot understanding, tool-calling investigations, follow-ups),
the real-world scheduled-task diagnostic case, Milestone 003 (registry-only
corrective actions, single-use human approval, demo-worker recovery,
independent verification, SQLite persistence, Markdown/JSON export, Windows
error-code interpretation), Milestone 004 (three-stage workstation,
reproducible demo scenarios, Playwright e2e, demo ops scripts, CI, demo
package), Milestone 005 (split approve/execute UX with expiry recovery,
16-case diagnostic gauntlet with live-model evals, phantom safe-guidance,
static recorded jury demo), and Milestone 006 (application-crash and
process/service/DNS diagnostics, symptom triage planner, incident overview,
evidence-linked runbook steps, technician notes, 34-case gauntlet, Windows
field testing) were all designed and implemented during the event.

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
