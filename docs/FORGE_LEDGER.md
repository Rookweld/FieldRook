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

## Phase B orchestration note

Workflow-tool Phase B launch FAILED pre-work: all 5 `parallel` items
returned `invalid_host_call`. Only delta vs the working Phase A script
was `isolation: true` — runtime workflow isolation is unusable here.
Fallback (per directive): `subagent_spawn` with `worktree_isolation`.
ALSO rejected: `workspace_git_probe_failed` — session root
(C:\Users\pontu) is not the repo, so the runtime cannot isolate.
Final fallback (in effect): shared-checkout children that each
self-create a real `git worktree` under C:\tmp\forge-wt-<agent>
(first command) and write ONLY there. Main checkout is read-only
for children except the single `worktree add`.

## Phase B (parallel implementation)

| agent | branch | base | deliverables | tests | status |
|---|---|---|---|---|---|
| ALPHA collector | `forge/alpha-collector` | ded3b17 | 16 new, 0 edits (741716f) | 96 passed, verified by lead | MERGED |
| BETA toolpacks | `forge/beta-toolpacks` | ded3b17 | 7 new, 0 edits (53eef3e) | 26 passed, verified by lead | MERGED |
| GAMMA knowledge | `forge/gamma-knowledge` | ded3b17 | 11 new, 0 edits (8b46661) | 36+1 passed after lead CRLF-hash fix | MERGED |
| DELTA engine | `forge/delta-engine` | ded3b17 | 2 new + loop/local_tasks/assist only (c2127ad) | full 394 green, verified by lead | MERGED |
| EPSILON workstation | `forge/epsilon-workstation` | ded3b17 | 13 new, 0 edits (1c97bc6) | spec runs after lead wiring (step 7) | MERGED |

Integration branch: `forge/integration`. Lead step 1 (schemas/state/
persist/export 1.1 + 3 tests) committed as `7798ea1`. Combined gate:
**556 passed**. Integration fix `53fa9f7`: LF-normalized corpus
hashing + `.gitattributes` + CRLF regression test (git autocrlf had
invalidated GAMMA's manifest hashes at merge).

Rules: new-files-only except DELTA (see contracts §6). No agent
touches another agent's paths. No pushes. Offline: no cloud calls,
no model downloads. Test runner for backend agents without a venv:
`C:\dev\FieldRook\backend\.venv\Scripts\python.exe -m pytest`
from the worktree `backend/` dir (read-only use; never modify it).

## Integration order (§7)

0. contracts (this branch) → 1. lead schemas → 2. BETA →
3. ALPHA → 4. DELTA → 5. turn/import wiring (lead) → 6. GAMMA →
7. EPSILON → 8. export/security → 9. ZETA.
