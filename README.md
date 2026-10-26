# FieldRook — Diagnose. Verify. Resolve.

Evidence-driven AI troubleshooting assistant for IT technicians. A ROOKWELD
project built for the Meta Global AI Developer Hackathon 2026 (Indie Developer
track, "Build for Your World").

**Milestone 002 — Eyes of the Raven:** describe a problem in natural language,
optionally attach a screenshot, and let Muse Spark drive a bounded, read-only
tool-calling investigation. Every conclusion stays traceable to evidence framed
as **OBSERVED** (measured), **INFERRED** (AI hypothesis), or **UNVERIFIED**
(unknown or missing).

## Layout

- `backend/` — Python + FastAPI: strict read-only tool registry (services,
  event logs, OS, network), Meta tool-calling loop, session investigations,
  screenshot intake, pytest suite.
- `frontend/` — React + TypeScript + Vite: problem workstation (intake,
  activity timeline, evidence cards, assessment, follow-ups) plus the original
  Milestone 001 service lookup tab.

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

### 3. Tests

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
| GET | `/api/investigations/{id}` | Current investigation state |
| POST | `/api/investigations/{id}/followup` | Continue: `{"message": "..."}` |

## Safety

Strictly read-only: services, event logs (System/Application), OS info, and
network state are only ever read through predefined, schema-validated tools
(bounded budget: 8 initial + 4 per follow-up tool calls, 12 total; per-tool
timeouts; truncated results). The model can never
send executable commands. No service control, network resets, registry edits,
installations, or privilege escalation exist. Screenshots are validated
(PNG/JPEG, magic bytes, 5MB cap), require explicit sharing consent, are sent to
the Meta API only with that consent, and are never stored by FieldRook.
