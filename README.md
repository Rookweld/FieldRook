# FieldRook — Diagnose. Verify. Resolve.

Evidence-driven AI troubleshooting assistant for IT technicians. A ROOKWELD
project built for the Meta Global AI Developer Hackathon 2026 (Indie Developer
track, "Build for Your World").

**Milestone 001 — The First Diagnosis:** a technician selects a Windows service,
FieldRook gathers real diagnostic evidence, the AI analyzes it, and the app
displays an evidence-backed incident assessment.

Defining principle: **FieldRook distinguishes what the AI believes from what
the system can actually prove** — every statement is framed as
**OBSERVED** (measured), **INFERRED** (AI hypothesis), or **UNVERIFIED**
(unknown or missing).

## Layout

- `backend/` — Python + FastAPI: allowlisted read-only Windows diagnostics,
  Meta Model API provider with simulated fallback, incident endpoints, pytest suite.
- `frontend/` — React + TypeScript + Vite: dark technician UI.

## Prerequisites

- Windows 10/11 with PowerShell (live diagnostics; fixtures work anywhere)
- Python 3.12+
- Node.js 20+ with npm (or pnpm)

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
- **Analysis:** live Meta Model API (`muse-spark-1.3`) when `MODEL_API_KEY` is
  set; otherwise clearly labeled simulated analysis. Simulated output is never
  presented as a live model call.

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/status` | Backend status, platform, active modes |
| GET | `/api/services` | List Windows services (live or fixture) |
| GET | `/api/services/{name}/diagnostics` | Evidence bundle for one service |
| POST | `/api/incidents/analyze` | Full assessment: `{"service_name": "...", "use_fixtures": null}` |

Optional query/body flag `use_fixtures` (`true`/`false`/absent) overrides the
`FIELDROOK_FIXTURES` default per request.

## Safety

Milestone 001 is strictly read-only: `Get-Service`, `Get-CimInstance
Win32_Service`, and bounded `Get-WinEvent` reads only. No service control,
registry edits, or privileged operations exist, and the test suite asserts that
no system-modifying route is exposed.
