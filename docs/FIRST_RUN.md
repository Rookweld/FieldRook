# FieldRook First-Run Guide

Get from zero to your first evidence-backed diagnosis in about ten
minutes. No admin rights needed; FieldRook only reads your system until
you explicitly approve the one demo action.

## 1. What you need

- Windows 10/11 with PowerShell (live diagnostics; without it you get
  clearly labeled fixtures)
- Python 3.12+
- Node.js 20+ with `pnpm` (or `npm`)
- Optional: a `MODEL_API_KEY` for live Meta Muse Spark reasoning. Without
  it, FieldRook uses clearly labeled deterministic simulated analysis —
  everything still works.

## 2. Start the backend

```powershell
cd C:\dev\FieldRook\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item ..\.env.example ..\.env   # optional; set MODEL_API_KEY inside for live model calls
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave that window running. The API listens on localhost only.

## 3. Start the frontend

```powershell
cd C:\dev\FieldRook\frontend
pnpm install
pnpm run dev
```

Open <http://localhost:5173>.

## 4. Read the badges first

Top-right badges tell you what is real and what is not:

| Badge | Meaning |
| ----- | ------- |
| `LIVE MODEL` / `SIMULATED MODEL` | Who is reasoning: Meta Muse Spark, or the deterministic fallback |
| `LIVE DIAGNOSTICS` / `FIXTURES ONLY` | Host capability: this machine can run real read-only diagnostics, or not |
| Per-investigation `FIXTURES` / `LIVE DIAGNOSTICS` | Evidence source for *that* investigation |

Hover any badge for the full explanation. If live diagnostics fail
mid-run, the evidence card says so instead of silently substituting
fixtures.

## 5. Your first investigation (safe)

1. Click the **Service lookup** tab, pick `wuauserv` (Windows Update),
   click **Investigate**. This runs read-only PowerShell queries and
   typically finishes in under a minute.
2. Go back to **Investigate problem** and describe a symptom in your own
   words, e.g. "Has Excel crashed on this machine in the last day?"
   Live investigations take roughly 15–45 seconds: the model calls
   tools, then writes an evidence-cited assessment.
3. Read the **Findings** view first: the result header states the
   primary finding, the honest status, and the single recommended next
   step. Below it are the diagnosis, open questions, and any historical
   matches. Cyan `OBSERVED` facts are measured; grey `INFERRED` causes
   are hypotheses; amber `UNVERIFIED` items are missing or unknown.
   Every claim cites `ev-N` chips — click one for a quick preview
   (the page will not jump); choose "Go to full evidence" only when you
   want the **Evidence** view. The **Resolve** view holds corrective
   actions, resolution plans, verification, and report export.

## 6. What FieldRook will and will not do

- Diagnostics are read-only and bounded (timeouts, result caps, evidence
  truncation is labeled on the card).
- The only thing FieldRook can ever change is its own demo worker, and
  only through propose → approve → execute with a single-use token.
  Everything else is guidance for you to carry out.
- A "Done" click is a claim, never proof: Confirm Fix re-measures with
  independent diagnostics and grades `VERIFIED_RESOLVED`,
  `NOT_RESOLVED`, or `INCONCLUSIVE`.

## 7. Where your data lives

- Investigations, notes, plans, and the knowledge library persist in
  `backend/data/fieldrook.db` (SQLite, local only). Override with
  `FIELDROOK_DB_PATH`.
- History reopens anything; the Knowledge tab manages remembered
  incidents (search, inspect, export one entry, delete).
- Nothing leaves localhost except explicit live-model API calls, which
  carry only the current redacted investigation context.

## 8. Stopping

Stop both terminal windows (`Ctrl+C`). To remove all local state,
delete `backend/data/fieldrook.db` and the `demo_worker/state/`
directory while the servers are stopped.
