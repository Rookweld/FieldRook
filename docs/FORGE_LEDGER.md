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

## M022 checkpoint (knowledge-backed investigation)

- Found the DELTA seam half-dead: build_investigation_messages took
  knowledge_excerpts but no caller passed any; state had no excerpt
  fields. Collector arrival notes worked; reference context never did.
- Fix: reference_excerpts_for() fresh per turn (fail-closed), wired
  into initial cloud turn, collector-arrival re-injection (once per
  conversation), and local triage/reassess prompts (optional param,
  byte-identical default). Quoted user-message blocks only; system
  prompt never sees excerpt text (pinned by test).
- Retrieval gap fixed: evidence terms kept snake_case whole
  ('dns_config' vs corpus 'dns'), so terms never matched. Split to
  sub-tokens in helper + references endpoint; printer case 0->3.
- Cycle dodge: module-level knowledge import in loop.py cycles via
  knowledge/__init__ -> service -> loop; deferred to call time.
- Live proof: 1 production-path triage call to qwen3:4b (loopback,
  think off) with 3 excerpts -> valid JSON, zero warnings,
  discriminating DNS-server question. Citation integrity enforced by
  existing validator (_known_only drops fabricated ids).
- Note: evidence terms (W_EVIDENCE=2) can outrank problem match;
  GAMMA owns weight tuning, unchanged here.
- Gates: backend 578, E2E 39/39, gauntlet 37/37, build clean.

## M023 checkpoint (unified technician workstation)

- Contextual dock: exactly one turn composer and one notes input on
  screen at all times (guide hides dock composer, findings hides dock
  notes, evidence/resolve show both). hideComposer/hideNotes flags on
  RespondDock, forwarded by WorkspaceShell, derived from view.
- Mobile overflow fixed: 390px scrollWidth was 759 (nowrap queue rows
  forced grid min-content). min-width:0 on forge grid children +
  wrap-on-mobile for queue rows (rule must trail the base nowrap
  rule; first placement lost on source order, caught by screenshot).
  Atmosphere svg boxes measured wide but are fixed/clipped decor.
- Spec: contextual twin test + 390px no-overflow test (9 forge E2E).
- Intake collector card verified coherent (no change needed).
- Gates: E2E 41/41, tsc + build clean (backend 578 unchanged).

## M024 checkpoint (product validation & distribution)

- `start-fieldrook.bat`: one-command Windows starter (backend :8000 +
  frontend :5173, localhost only, preflight checks). Mechanics
  execution-validated via a test-port copy (:8123/:4173 both HTTP
  200, PID-verified stopped); the shipping file itself was NOT run
  because the operator's live stack holds :8000/:5173.
- `docs/FORGE_PRIVACY.md`: evidence-based review (binds, consent,
  redaction, untrusted-import handling, quoted-only excerpts,
  citation validation, secrets hygiene) + residual risks.
- README: FORGE capabilities, checkpoint stage line, 2 screenshots.
- Final gates: backend 578, E2E 41/41, gauntlet 37/37 exit 0,
  tsc + build clean, secret scan clean.
- Program total: 84 files, +11098/-42 vs master. No push.
- NOT re-run: full blind challenge on FORGE turns (budget); M019
  challenge numbers stand; knowledge context is additive quoted
  text with byte-identical defaults when absent.

## M024.1 hardening (target isolation, blind eval, readiness)

- Reverify boundary: collector-imported / remote-target evidence
  can no longer trigger host-local remeasurement (422/409 at the
  backend, UI mirrors); static `interpret_error_code` stays
  available. Regression tests in
  `backend/tests/test_m0241_target_isolation.py` + E2E no-recheck.
- Single-target import: a second computer's package into an
  associated case is rejected (409), not warned-and-mixed.
- Real collector run on Fury (read-only, safe out dir): 10
  entries, 0 errors, VALID, 8KB, no raw-hostname leak; import +
  recollect-all-unchanged verified live, incl. chunk slice c1.
  NOTE: the collector needs a Python interpreter on the target
  (stdlib-only). No standalone exe exists; see
  `docs/DISTRIBUTION.md` for the route.
- Blind eval on integrated FORGE (`backend/eval/challenge/
  REPORT_M0241.md`): held-out 45/53 x3 (M019: 48/53) with one
  systematic retrieval-priming regression (cad 9/9 -> 7/9); new
  FORGE suite 47/50 + 44/50. CORRECTION to the M024 note above:
  knowledge context is NOT behavior-neutral - irrelevant
  retrievals measurably distract the small model. Relevance
  gating is recommended future work.
- Launcher: `start-fieldrook.bat` documented as a DEVELOPMENT
  launcher (`docs/DISTRIBUTION.md`); failure modes verified via
  a test-port replica (missing venv/deps errors, pnpm/python
  absence, occupied-port split-brain with success message).

Validation status after M024.1:

| claim | status |
|---|---|
| reverify refuses wrong-computer rechecks | Implemented; unit + E2E tests; live Fury backend |
| single-target import association | Implemented; unit tests incl. live-host case |
| collector package validity/redaction | Tested on fixtures; tested on Fury (real run) |
| collector on a second machine | NOT validated (no second Windows box) |
| blind FORGE behavior beyond fixtures | Tested on Fury (GPU, qwen3:4b, 11 scenarios) |
| independent-hardware validation | NOT validated (Fury only) |
| 8GB CPU-laptop interactivity | NOT validated (M019 true-CPU FAIL stands) |
| standalone distribution | NOT delivered (route defined, dev launcher only) |

## M024.2 hardening (knowledge relevance gate)

- M024.1's blind eval caught retrieval priming (cad 9/9 -> 7/9 stable):
  `ref-service-recovery` retrieved on generic filler (client/needs/
  review). Fix: `backend/app/knowledge/relevance_gate.py`, a
  conservative second-stage filter over unchanged ranking. A passage
  is kept iff error-code match, discriminating title/heading topic,
  discriminating evidence term, or >=2 distinct discriminating
  problem/service terms (df<=3 + ~700-term generic vocabulary).
  Ranking, scores, citations, and quoted-excerpt boundaries unchanged.
- First revision (df<=2, single-term OR) over-filtered the genuinely
  topical stopped-service query (F3 refs [] 3/3); the suite caught it
  and the shipped revision keeps coherent common-term combinations.
- Blind re-eval (`backend/eval/challenge/REPORT_M0242.md`, qwen3:4b,
  loopback, same conditions): held-out 46/53, 46/53, 47/53 (M024.1:
  45 x3; M019: 48, pre-fix spread 46-48); FORGE suite 45/50, 44/50,
  47/50 (M024.1: 47, 44). CAD recovered 9/9, 8/9, 9/9 with zero
  excerpts; gate-off ablation reproduces M024.1's 7/9 exactly
  (causal proof). Relevant retrieval preserved: DNS guided 3/3,
  collector-DNS narrowed 3 docs -> 1, required service retrieval 3/3
  with no-service-cause 3/3.
- Residuals: F3 also pulls weakly relevant ref-error-codes via a
  common-term pair (no measured harm, same 9/10); frozen-window
  contradiction/scoped disagreements unchanged; single-term topical
  queries now yield silence (accepted).
- Gates: pytest 607/607 (17 new), gauntlet 37/37 exit 0, E2E 42/42,
  tsc + build clean, secret scan clean (grep fallback, benign
  tokenizer prose only). No harness/rubric/scenario changes.
- Validation-status deltas vs M024.1: blind FORGE re-evaluated post-
  gate (Fury, GPU, qwen3:4b, 11 scenarios x3 + ablation); second
  machine / independent hardware / 8GB laptop / standalone remain
  NOT validated (unchanged). HACKATHON rows for M024.1+M024.2 stay
  deferred to merge time. No push. Branch ready for merge pending
  authorization (M024.2 verdict in REPORT_M0242.md section 10).
