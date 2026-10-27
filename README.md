<div align="center">

# 🐦‍⬛ FieldRook
### Diagnose. Verify. Resolve.

**Evidence-driven AI troubleshooting for Windows technicians.**

Turn a reported symptom into an investigation with traceable evidence, technician-controlled recovery, and independently verified outcomes.

[![CI](https://github.com/Rookweld/FieldRook/actions/workflows/validate.yml/badge.svg)](https://github.com/Rookweld/FieldRook/actions/workflows/validate.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
![Meta AI Hackathon 2026](https://img.shields.io/badge/Meta_AI_Hackathon-2026-orange)

**[Quickstart](#quickstart) · [Demo walkthrough](docs/demo/DEMO_SCRIPT.md) · [How it works](#how-it-works) · [Safety](#safety)**

![FieldRook technician workstation](docs/assets/fieldrook-workstation.png)

</div>

## Why FieldRook?

IT diagnosis often means switching between service managers, Windows event logs, scheduled tasks, network tools, and documentation. FieldRook brings the investigation into one local-first workstation. **Meta Muse Spark chooses from bounded diagnostic tools; FieldRook collects evidence and enforces the safety boundary.** The model does not get unrestricted shell access or final authority over whether a fix worked.

| Investigate | Understand | Resolve |
| :-- | :-- | :-- |
| Describe symptoms, optionally provide a screenshot. | Inspect real tool activity, evidence IDs, and clearly labeled uncertainty. | Review a proposed action, approve explicitly, and compare independent before/after checks. |

### A real investigation, not a mockup

The example below uses a **clearly labeled synthetic fixture** based on a real class of recurring PowerShell-window issues. It is not a claim that the same issue is currently active.

![FieldRook investigation timeline](docs/assets/fieldrook-investigation.png)

<details>
<summary>View evidence-backed diagnosis screenshot</summary>

![FieldRook evidence-backed assessment](docs/assets/fieldrook-evidence.png)

</details>

## How it works

```text
Technician reports symptoms
          |
          v
Meta Muse Spark plans and requests approved diagnostic tools
          |
          v
Read-only Windows collectors -> timestamped evidence -> cited hypotheses
          |
          v
Optional registered corrective action -> explicit technician approval
          |
          v
Constrained execution -> fresh independent health check -> incident report
```

**Built during the Meta Global AI Developer Hackathon 2026.** See [HACKATHON.md](HACKATHON.md) for the development timeline and [technical highlights](docs/demo/TECHNICAL_HIGHLIGHTS.md) for the implementation boundaries. The only corrective action currently supported targets FieldRook's own demo worker; real Windows diagnostics are read-only.

---

# FieldRook — Diagnose. Verify. Resolve.

Evidence-driven AI troubleshooting assistant for IT technicians. A ROOKWELD
project built for the Meta Global AI Developer Hackathon 2026 (Indie Developer
track, "Build for Your World").

**Milestone 004 — The Field Demonstration:** the M003 controlled-fix loop is
now a polished three-stage technician workstation — **Investigate → Understand
→ Resolve** — with three reproducible demo scenarios: (A) a phantom PowerShell
scheduled task diagnosed from fixtures, (B) the full live loop of failure,
human approval, fenced recovery, and independent `VERIFIED_RESOLVED`, and (C)
an insufficient-evidence case that reports `UNRESOLVED` honestly instead of
inventing certainty. Corrective actions come only from a predefined backend
registry, require explicit single-use human approval, and are verified by fresh
diagnostics, never by model confidence. Incidents persist in SQLite, export to
Markdown/JSON, and every conclusion stays traceable to evidence framed as
**OBSERVED** (measured), **INFERRED** (AI hypothesis), or **UNVERIFIED**
(unknown or missing).

## Layout

- `backend/` — Python + FastAPI: strict read-only tool registry (services,
  event logs, OS, network, scheduled tasks, demo-worker health, error codes),
  Meta tool-calling loop, corrective-action subsystem (`app/actions/`:
  registry, policies, approval, executor, verification, audit), SQLite
  persistence, incident export, pytest suite.
- `demo_worker/` — application-owned background process with a heartbeat health
  check plus a failure simulator for the controlled-fix demonstration.
- `frontend/` — React + TypeScript + Vite: problem workstation (intake,
  activity timeline, evidence cards, assessment, follow-ups), Action Center
  (approve/reject, before/after, executions), incident history with export,
  plus the original Milestone 001 service lookup tab. Playwright e2e suite
  under `frontend/tests/e2e/`.
- `scripts/demo/` — demo operations: preflight, worker start, failure
  injection, health checks, and reset (no admin rights needed).
- `docs/demo/` — three-minute demo script, demo-day checklist, technical
  highlights, and judging notes.

## Prerequisites

- Windows 10/11 with PowerShell (live diagnostics; fixtures work anywhere)
- Python 3.12+
- Node.js 20+ with pnpm (recommended) or npm

## Quickstart

### 1. Backend

```powershell
cd C:\dev\FieldRook\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item ..\.env.example ..\.env   # optional; set MODEL_API_KEY for live model calls
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend

```powershell
cd C:\dev\FieldRook\frontend
pnpm install
pnpm run dev
```

(`npm install` / `npm run dev` are an alternative if you prefer npm.)

Open <http://localhost:5173>. The Vite dev server proxies `/api` to the backend.

### 3. Demo operations (Scenario B)

```powershell
cd C:\dev\FieldRook
powershell -ExecutionPolicy Bypass -File scripts/demo/preflight.ps1     # readiness
powershell -ExecutionPolicy Bypass -File scripts/demo/start-worker.ps1  # healthy worker
powershell -ExecutionPolicy Bypass -File scripts/demo/inject-failure.ps1 # inject the fault
powershell -ExecutionPolicy Bypass -File scripts/demo/check-health.ps1  # worker + backend
powershell -ExecutionPolicy Bypass -File scripts/demo/reset-demo.ps1    # healthy again
```

Set `$env:FIELDROOK_PYTHON` to override the interpreter if the venv lives
elsewhere. See `docs/demo/DEMO_SCRIPT.md` for the three-minute run.

### 4. Tests

```powershell
cd C:\dev\FieldRook\backend
.\.venv\Scripts\python -m pytest -q
cd ..\frontend
pnpm run test:e2e   # Playwright: real backend (fixtures, no key) + real UI
```

## Modes

- **Diagnostics:** live PowerShell collection on Windows; deterministic fixtures
  when unavailable, or forced with `FIELDROOK_FIXTURES=always`.
- **Analysis:** live Meta Model API (`muse-spark-1.3`, tool calling + vision)
  when `MODEL_API_KEY` is set; otherwise clearly labeled simulated analysis.
  Simulated output is never presented as a live model call.

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/status` | Backend status, platform, active modes |
| GET | `/api/tools` | Read-only diagnostic tool registry |
| GET | `/api/services` | List Windows services (live or fixture) |
| GET | `/api/services/{name}/diagnostics` | Evidence bundle for one service |
| POST | `/api/incidents/analyze` | M001 assessment: `{"service_name": "...", "use_fixtures": null}` |
| POST | `/api/investigations` | Start NL investigation (multipart: `problem`, optional `service_name`, `screenshot` + `share_consent`, `use_fixtures`) |
| GET | `/api/investigations` | Incident history (persisted, `?limit=`) |
| GET | `/api/investigations/{id}` | Current investigation state |
| POST | `/api/investigations/{id}/followup` | Continue: `{"message": "..."}` |
| GET | `/api/investigations/{id}/export?format=markdown\|json` | Ticket-ready incident report |
| POST | `/api/investigations/{id}/proposals` | Propose a registered action (never executes) |
| POST | `/api/proposals/{id}/approve` | Human approval → single-use token (5 min TTL) |
| POST | `/api/proposals/{id}/reject` | Human rejection → system left unchanged |
| POST | `/api/proposals/{id}/execute` | Run approved action: `{"approval_token": "...", "args": {...}}` |

## Safety

Diagnostics are strictly read-only: services, event logs (System/Application),
OS info, network state, scheduled task definitions, demo-worker health, and
error codes are only ever read through predefined, schema-validated tools
(bounded budget: 8 initial + 4 per follow-up tool calls, 12 total; per-tool
timeouts; truncated results). The model can never send executable commands.

The one corrective capability — `recover_demo_worker` on the
application-owned `demo-worker` — is fenced by: registry-only actions, target
allowlist, schema-validated arguments, live preconditions, explicit human
approval (single-use token, 5-minute TTL, exact-argument binding, invalidated
if the investigation changes), single-flight execution with timeout,
fenced worker-process verification, independent post-action verification
(`VERIFIED_RESOLVED` etc., never overridable by the model), localhost binding,
cross-origin mutation blocking, and a full audit trail persisted in SQLite.
Rejection leaves the system unchanged. Set `FIELDROOK_ACTIONS_ENABLED=0` to
disable all corrective actions while keeping diagnostics.

No arbitrary shell execution, service control, network resets, registry edits,
installations, or privilege escalation exist. Screenshots are validated
(PNG/JPEG, magic bytes, 5MB cap), require explicit sharing consent, are sent to
the Meta API only with that consent, and are never stored by FieldRook.
Approval tokens are stored as hashes only; the database and demo state live in
gitignored local paths (`backend/data/`, `demo_worker/state/`).

## Local-only security notice

FieldRook binds to localhost (`127.0.0.1:8000` backend, `localhost:5173` UI)
and rejects cross-origin browser mutations. Do not expose either service to a
network, do not run the corrective-action endpoints on shared infrastructure,
and never commit a real `.env` containing `MODEL_API_KEY`.
## Known limitations

- One corrective action only (`recover_demo_worker` on the application-owned
  demo worker); the registry is intentionally minimal.
- No per-user authentication; localhost binding is the access boundary.
- Browser end-to-end tests cover key flows via Playwright; live model calls remain separate smoke tests.
- Large investigation histories can approach the 60s model timeout.
- Model output is advisory: verification outcomes are computed by backend
  diagnostics and can never be overridden by the model.
## License

Copyright 2026 ROOKWELD (Pontus Lindh). Licensed under the Apache License,
Version 2.0 -- see [LICENSE](LICENSE) for the full text.
