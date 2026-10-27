# FieldRook — Demo Checklist

Use on demo day. Check each box in order; stop at the first failure.

## 1. Environment

- [ ] Windows 10/11, ordinary user (no admin needed).
- [ ] `scripts/demo/preflight.ps1` passes with zero `[FAIL]` lines.
- [ ] `.env` contains `MODEL_API_KEY` (else the demo runs simulated-only —
      still honest, but say so on camera).

## 2. Services

- [ ] Backend: `.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
      (from `backend/`). `/api/status` shows `model_mode: live`.
- [ ] Frontend: `pnpm run dev` in `frontend/`. Page loads at
      `http://localhost:5173` with no console errors.
- [ ] Worker: `scripts/demo/reset-demo.ps1` ends "worker healthy".

## 3. Scenario B arming

- [ ] `scripts/demo/inject-failure.ps1` ends "Failure injected: status=failed".
- [ ] `scripts/demo/check-health.ps1` shows `worker: status=failed`.

## 4. During the demo

- [ ] Investigation completes with `LIVE MODEL` + `LIVE DIAGNOSTICS` badges.
- [ ] Timeline shows a real `get_demo_worker_health` request and `ev-1`.
- [ ] Assessment facts carry clickable `ev-N` chips.
- [ ] Resolution banner reads UNRESOLVED before approval.
- [ ] Proposal card shows action, target, evidence, risk, verification.
- [ ] Worker is STILL failed after approval, BEFORE execution.
- [ ] After execute: outcome `VERIFIED_RESOLVED`, before/after `failed -> healthy`.
- [ ] History lists the incident; Markdown export downloads with 11 sections.

## 5. Fallbacks (if live API fails mid-demo)

- [ ] Say so on camera; do not fake it.
- [ ] Restart the backend without `MODEL_API_KEY` (or set `FIELDROOK_FIXTURES=always`)
      and re-run: badges flip to SIMULATED/FIXTURES, flow stays identical.
- [ ] Scenario A works fully offline with "Force fixture data" checked.

## 6. Teardown

- [ ] `scripts/demo/reset-demo.ps1` — worker healthy again.
- [ ] Stop frontend (Ctrl+C), backend (Ctrl+C), worker process.
- [ ] Saved demo investigations remain in `backend/data/` for review; delete
      the database file only if you explicitly want a clean slate.
