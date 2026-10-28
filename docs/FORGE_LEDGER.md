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

## Phase C (lead wiring + integration)

| step | commit | content | gate |
|---|---|---|---|
| 2 | `b87e35e` | import endpoint, 18-tool registry, 11 wiring tests | 565 + count-fix |
| 3-4 | `68b42bd` | references endpoint, EPSILON App mount, spec un-fixme + legacy scoping | 569 / 39 E2E / 37 gauntlet / build |

Legacy E2E scoping rationale: the workspace dock legitimately
duplicates turn composer / notes / queue-head controls, so page-wide
selectors became ambiguous. Scoped to `.view-panel` (same user-visible
capability, zero tests deleted). Evidence-visual scroll check now
settles scroll before measuring (click's own scroll was page height).

## Phase D (ZETA validation, lead-executed)

Report: `docs/FORGE_ZETA.md`. Secret scan clean (grep fallback).
Live probes 17/17. UI acceptance demo 4/4 screenshots.
Demo stack (:8123/:4173) PID-verified stopped; ports freed.
Operator :8000 stack untouched throughout.

## M020 checkpoint

Collector foundation: portable collect -> versioned package -> secure
import -> target-kept evidence -> investigation -> verified export.
Cut from `forge/integration`; no push (awaiting authorization).

## M021 checkpoint (diagnostic expansion hardening)

- Promoted the 4 BETA tools from PROPOSED_TOOLPACKS to wired families
  (devices: list_devices, list_volumes; office_local:
  list_office_installs, get_office_config); TOOLPACKS renamed, 18/18.
- REGISTRY<->families cross-check test (fail-closed on drift) + model
  exposure pin (local yes, remote no via HOST_MEASUREMENT_TOOLS).
- `/api/tools` gains additive `family`; frontend ToolInfo parity.
- Category labels for pnp_devices/volumes/office_* in both maps.
- Closed Phase A read gaps: windows_net.py:1-129,
  windows_tasks.py:130-319 (allowlisted scripts, sanitized shaping).
- Gates: backend 571, E2E 39/39, gauntlet 37/37, build clean.
