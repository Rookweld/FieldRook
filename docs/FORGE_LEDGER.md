# FORGE integration ledger

Program: OPERATION FIELDROOK — FULL FORGE. Base: `9284952` (M019).
Contracts: `docs/FORGE_CONTRACTS.md` (frozen v1).
Lead: integration owner. Branches merge into `forge/integration`
(checkpoints M020–M024 cut from there to master).

## Phase A (architecture)

| item | status | notes |
|---|---|---|
| Research workflow (6 scopes) | complete | evidence verified by lead; all cites real |
| Coherence critic | DISCARDED | hallucinated `.fieldrook-stage` tree; all judgments void |
| Synthesis spec | DISCARDED | poisoned by critic ("VERIFIED wins" inversion) |
| Lead contracts v1 | frozen | this branch; all refs lead-verified |

Unresolved from Phase A: `windows_net.py:1-129` and
`windows_tasks.py:130-319` live bodies not individually opened.
BETA opens them during toolpack work (owns new diagnostics).

## Phase B (parallel implementation)

| agent | branch | base | deliverables | tests | status |
|---|---|---|---|---|---|
| ALPHA collector | `forge/alpha-collector` | contracts HEAD | `collector/**`, `test_collector_*.py` | pytest collector suite | |
| BETA toolpacks | `forge/beta-toolpacks` | contracts HEAD | `backend/app/toolpacks/**`, `windows_<new>.py`, `test_toolpacks_*.py` | pytest toolpack suite | |
| GAMMA knowledge | `forge/gamma-knowledge` | contracts HEAD | `reference/**`, `reference_index.py`, `reference_service.py`, `test_knowledge_ref_*.py` | pytest knowledge suite | |
| DELTA engine | `forge/delta-engine` | contracts HEAD | loop/local_tasks/assist edits + `evidence_digest.py` | test_loop + test_local_tasks + test_assist green | |
| EPSILON workstation | `forge/epsilon-workstation` | contracts HEAD | `frontend/src/forge/**`, forge spec | tsc clean (lead runs build); spec at integration | |

Rules: new-files-only except DELTA (see contracts §6). No agent
touches another agent's paths. No pushes. Offline: no cloud calls,
no model downloads. Test runner for backend agents without a venv:
`C:\dev\FieldRook\backend\.venv\Scripts\python.exe -m pytest`
from the worktree `backend/` dir (read-only use; never modify it).

## Integration order (§7)

0. contracts (this branch) → 1. lead schemas → 2. BETA →
3. ALPHA → 4. DELTA → 5. turn/import wiring (lead) → 6. GAMMA →
7. EPSILON → 8. export/security → 9. ZETA.
