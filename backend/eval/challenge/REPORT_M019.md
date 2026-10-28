# M019 technician loop — report

M019 fixes the interaction loop using M018's measured failures: too many
model calls per turn, weak scoping questions, stale questions cluttering
the Guide, unsafe manual guidance, GPU-flavored CPU claims, and no
mid-flight cancel. One technician interaction now normally costs one
model decision; the Guide leads with one current question or step.

No cloud calls and no model downloads in M019. All model measurements
below are loopback Ollama under `FIELDROOK_OFFLINE=1` on Fury (RTX 3500
Ada for GPU runs; `num_gpu=0` + placement check for CPU runs).

## 0. M018-vs-M019 comparison (qwen3:4b, main suite, 20 scenarios)

Same harness, same rubric, identical scenario inputs. Checks are
structural (keyword/branch/state assertions), so small deltas are noise —
see the A/B note.

| run | code | checks | model calls |
|---|---|---|---|
| M018 record (`20261028T091333Z`) | bcb80ef | 132/142 | 234 |
| M019 pre-fix (`20261028T131434Z`) | uncommitted | 129/142 | 43 |
| M019 pre-fix (`20261028T132758Z`) | uncommitted | 131/142 | 66 |
| M019 post-fix (`20261028T142851Z`) | this commit | 127/142 | 50 |

Single-decision inference cuts calls ~4.7× (234 → 43–66 → 50).
Check totals move 132 → 127–131. The spread across identical-code runs
(129 vs 131) already exceeds the post-fix dip, and a targeted A/B
(slow-device, app-freeze, disproved-hypothesis with the plan-merge fix
reverted, `20261028T143454Z`) fails the *same* checks (onset, repro) at
identical scores — sampling variance, not a regression from the fix.

## 1. Held-out cases (6 unseen, qwen3:4b)

New `heldout_scenarios.py`, never used during M019 development:

| run | checks | calls |
|---|---|---|
| pre-fix (`20261028T133105Z`) | 46/53 | 30 |
| pre-fix (`20261028T133733Z`) | 48/53 | 22 |
| post-fix (`20261028T143606Z`) | 48/53 | 16 |

Post-fix matches the best pre-fix run at 48/53 with the fewest calls.
Remaining misses are scoping judgment (the model asks a generic question
instead of the discriminating one), not harness artifacts — and per the
milestone rules, no scenario-specific hardcoding was added.

## 2. What changed

**Single-decision inference** (`loop.py`, `local_tasks.py`). One triage
OR reassess call per technician turn; plan generation runs only as
recovery when no question or check stands alone. Measured above.

**Better questions.** Scoping policy in the triage prompt
(scope → timing → symptoms; no version/reboot openers; never ask what
evidence already shows; tool-answerable items become checks). Reassess
carries the last 6 asks with a no-repeat rule and anti-fixation prompt.

**Question lifecycle** (`assist.py`, `schemas.py`). open / answered /
superseded / retired / blocked. The Guide shows only CURRENT first;
history collapses into "Earlier questions"; nothing is deleted;
"Can't answer" marks a question unable → blocked.

**Plan-merge correctness** (`assist.py`). Questions merge before the
plan so same-round question/step pairs coexist (the question asks, the
step tracks); `CLARIFYING_QUESTION` trackers are exempt from the
duplicate-question guard (which otherwise substring-matches its own
"Answer: " prefix); skipped steps persist as history instead of being
wiped the next round. `guide.spec.ts` (5/5) proves the current step
survives answers and turns.

**Safety filter** (`guidance.py`, 17 tests). Deterministic 6-tier impact
classification (READ_ONLY … UNSUPPORTED_OR_UNSAFE) with fault-domain
relevance notes; unsupported tool names demote automation to manual
guidance. Advisory only — never an execution path.

**Streaming + cancel** (`provider.py`, `test_cancel.py` 13 tests).
Streaming Ollama generation with per-chunk cancellation (~0.2s abort,
was ~9s); `RoundCancelled` never swallowed; duplicate submits blocked.

**CPU-first profiles** (`local_profiles.py`, `local_bench.py`).
Placement-verified `num_gpu=0` runs recorded per model; 1B marked
do-not-select; gemma noted best-quality but not CPU-interactive.

**Guide UX.** Current-focus card, collapsed history, safety badges,
profile warnings, live model name in the header, elapsed-time + cancel
during turns.

## 3. True-CPU verdict (unchanged: FAIL on interactivity)

Placement-verified CPU-only triage: qwen3:4b ~25–33s, llama3.2:3b
~16–32s, llama3.2:1b ~8–16s (fast but unacceptable quality/safety —
not a supported reasoning model). Best warm CPU turn ≈ 24s against a
10s target. No 8 GB laptop claim: all measurements are Fury; lower-spec
hardware was unavailable. The profiles say this honestly in-product.

## 4. Human-in-the-loop demo (genuine local inference)

`docs/assets/fieldrook-m019-tour.webm` (38s) + 3 screenshots. Wrong-code
Excel case through qwen3:4b: Q1 "Which specific Excel files are
affected?" → technician scopes (any file incl. blank) and corrects the
code to 0x80040154 → "Corrupted Excel files" hypothesis WEAKENED with
history → reassessment names the corrected code → `/safe` add-in check
leads as CURRENT step. No scripted answers; model wording varies run to
run (assertions are structural).

## 5. Verification gates

- Backend pytest: **379 passed**
- Playwright E2E: **32 passed** (incl. 5 guide specs)
- Diagnostic gauntlet (offline): **37/37**, exit 0
- Frontend `tsc --noEmit && vite build`: clean
- Secret scan: no gitleaks binary; manual pattern scan over every
  changed/added file — only pre-existing dummy fixtures
  (`test-key-not-real`, M016 `hunter2`) and `sk-` prose matches
- Challenge: main 127/142 + heldout 48/53 post-fix (above)

## 6. Known limitations

- CPU interactivity FAIL stands (§3); GPU runs are fine (~2–4s/call).
- Scoping misses remain on held-out cases (model judgment, §1).
- Muse Spark: strongest scoping but verbose/repetitive; uncapped.
- Local vision stays expensive and fragmented; text fallback documented.
- Blind human grades cover 4 samples only.
- Operator :8000 stack untouched; isolated ports/DBs throughout.

## 7. Invocation accounting

~120 loopback Ollama calls for the post-fix verification in this
session (main 50 + heldout 16 + A/B 10 + demo/E2E backends + probes).
Zero cloud calls, zero downloads. Earlier M019 benchmarking totals were
recorded during the milestone's first session.
