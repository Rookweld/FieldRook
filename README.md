# FieldRook — Diagnose. Verify. Resolve.

Evidence-driven AI troubleshooting assistant for IT technicians. A ROOKWELD
project built for the Meta Global AI Developer Hackathon 2026 (Indie Developer
track, "Build for Your World").

**Milestone 003 — The Controlled Fix:** the investigation workstation from
Milestones 001/002 now completes the loop — **diagnosis → proposed correction
→ human approval → controlled execution → independent verification** — against
an application-owned demo worker. Corrective actions come only from a
predefined backend registry, require explicit single-use human approval, and
are verified by fresh diagnostics, never by model confidence. Incidents persist
in SQLite, export to Markdown/JSON, and every conclusion stays traceable to
evidence framed as **OBSERVED** (measured), **INFERRED** (AI hypothesis), or
**UNVERIFIED** (unknown or missing).

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
  plus the original Milestone 001 service lookup tab.

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

### 3. Demo worker (for the controlled-fix scenario)

```powershell
cd C:\dev\FieldRook
.\backend\.venv\Scripts\python demo_worker/worker.py   # healthy heartbeat loop
.\backend\.venv\Scripts\python demo_worker/simulate_failure.py   # inject the fault
```

### 4. Tests

```powershell
cd C:\dev\FieldRook\backend
.\.venv\Scripts\python -m pytest -q
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
