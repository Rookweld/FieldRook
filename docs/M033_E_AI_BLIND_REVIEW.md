# M033-E — Locked Blind AI Review & Targeted Ranking Safeguards

**Date:** 2026-11-18
**Branch:** `m033/ai-audited-information-gain` (from M033-D `46ada45`)
**Public release:** `v0.6.0-rc.2`, **unchanged**
**Review provenance:** `AI_SINGLE_PASS` / `AI_RATED`; NOT a human technician score.

## 1. What was done, with provenance

The 12 **already generated** M033-D transcripts were all read, judged,
and scored while anonymized, **before** the private answer key was
opened. Each score follows the original 3+3+2+2 rubric, with a
specific written rationale. No score was changed after unblinding.

The original human review pack was not changed:
`backend/eval/results/m033d-first-blind/` (original
`review/scores.json` SHA-256
`4E9A7C358A6C617E7F6C8FC0CC941678B6383DA07C9A4B0AFBF04F08F6223B0F`,
UNRATED, 0/12 filled at review time).

A complete **separate copy** was graded under
`backend/eval/results/m033d-ai-audit/`:

- `review/scores.json`: 12 AI grades with 12 written rationales.
- `private/AI_RESULTS.json`: automatically unblinded **after** all
  grades passed schema, integrity and numeric-range validation.
- The original human review scores and private answer key remained untouched.
- No synthetic grades were presented as a technician's review.

`backend/eval/m033d_review.py` now supports strict review provenance:
an AI-labelled score pack produces **`AI_RESULTS.json`**, never
`HUMAN_RESULTS.json`. The existing human validator continues
to produce `HUMAN_RESULTS.json` for actual human scores.
Mismatched reviewer identities/statuses are rejected. Unit tests
exercise both flows.

## 2. Actual blind AI results

| Model | M033-B baseline (3 cases) | M033-C experiment (3 cases) |
| --- | ---: | ---: |
| Qwen3:4B | 6.00 / 10 | **7.00 / 10** |
| Qwen3:8B | **4.67 / 10** | 4.33 / 10 |

Individual matched cases (baseline → experiment):

| Case | Qwen3:4B | Qwen3:8B |
| --- | --- | --- |
| Blue screen after driver | 7 → 5 | 3 → 6 |
| CAD license checkout | 5 → 7 | 7 → 5 |
| Teams camera black | 6 → 9 | 4 → 2 |

**Interpretation:** no consistent superiority for M033-C. The
improvement for 4B in the camera case did not generalize to all
models/cases. Some apparent losses may be sampling variability. The
evaluator was GPT-6, which is *itself AI*, not a statistically
independent ground-truth judge. No blinded human scores yet exist.
Only three distinct cases per model/version were graded. Therefore:
**keep M033-C in `observe` (shadow) by default; no global `enforce`.**

## 3. Specific qualitative failures discovered

1. **Fabricated evidence scope:** The Teams-camera transcript
   inferred failure on multiple devices from reports about two
   applications on a single laptop. Different applications do not
   imply different machines.
2. **Contradictory hypothesis transition:** In one BSOD case the
   model weakened its driver-conflict hypothesis immediately after
   learning Windows Update had installed a new network driver.
3. **Insufficient service-health proof:** A failed `ping` to a
   license server was treated as proving the licensing service was
   down or its network configuration was wrong. ICMP response does
   not determine whether the application licensing port is open.
4. **Question repetition:** The camera had already been tested in
   the Windows Camera app; some candidates asked about that same
   result again or proposed circular tests.
5. **Untested scope assumptions:** Missing a driver file in a BSOD
   code does not independently demonstrate bad RAM; a dump timestamp
   alone does not tell us whether the driver caused the crash.

These are **examples observed in the transcripts**, not a claim
that every response has those problems.

## 4. Concrete fixes implemented (M033-E)

### A. Review provenance

- Added `AI_RATED` / `AI_SINGLE_PASS` to the offline M033-D
  validator, with a distinct unblinded AI output and no change to
  human score semantics.
- Added tests that AI reviews cannot impersonate a human review,
  and cannot be unblinded with mismatched provenance.

### B. Evidence-aware experimental next-step ranking

In `app/analysis/information_gain.py`:

- New bounded `already-answered-question` signal penalizes
  substantially repeated questions when the technician has
  provided an actual answer. Distinct comparison questions about
  the same application should remain eligible.
- New `already-answered-check` applies the same signal to manual
  technician checks.
- New `icmp-not-service-health` reduces (but does not prohibit)
  ranking of `ping` as evidence of application/server availability.
  Ping is still a valid basic IP connectivity test when relevant.

In `app/analysis/loop.py`:

- Passes only **genuinely answered** question/answer pairs into
  the ranker (excluding the existing explicit empty-answer
  detector's no-information replies).
- Records short, fixed vocabulary ranking-signal labels in the
  activity audit for explanation without copying prompt contents.

**Safety and scope:** These are bounded heuristics, not semantic
truth detectors. They run only in `observe` or `enforce`;
default `observe` logs the candidate ranking without changing
model decisions or prompts. They do not execute tools, grant
permissions, remove valid evidence or change the released rc.2.

## 5. Remaining limitations and next experiments

- Stop **unsupported hypothesis downgrades after substantive new
  information** only when grounded: the current deterministic
  M033-B safeguard correctly handles missing information but does
  not validate all logical supports/contradictions.
- Expand factual provenance beyond hex error codes to
  distinguish reports about applications, machines and services.
  Avoid a fragile hardcoded keyword list that blocks legitimate
  technician investigation.
- Add repeated and counterbalanced local-model benchmark runs,
  frozen case inputs, blinded independent technician grading,
  and report variation before claiming measured improvement.
- The M033-D human review remains available and untouched if an
  independent comparison is later desired.

## 6. Verification and release isolation

- Blind scoring lock: all 12/12 scored with rationales **before
  unblinding**; AI evaluation exit code 0.
- Original human `scores.json` unchanged (hash verified before/after),
  `status=UNRATED`, no `HUMAN_RESULTS.json` produced.
- Dedicated AI output includes `reviewer_type=AI_SINGLE_PASS` and
  score fields explicitly named `ai_score_out_of_10` /
  `mean_ai_score`; no human scores were forged.
- Full Python backend run: **839 passed, 4 skipped, 0 failed**,
  exit code 0, 385.93 seconds, 2 known warnings.
- After the final limited scoring-heuristic refinement and its
  new regression, **107 relevant final-source tests passed**, exit 0.
  The entire backend suite was not rerun a second time for
  that final limited change; do not represent it as such.
- Python compilation and Git whitespace/diff validation passed.
- All changes isolated to a local development branch; `master`,
  `origin/master`, `VERSION`, and published rc.2 untouched.

**This report represents the locked, original blind AI scores,
not retrospectively optimized numbers.** Any future revision needs
fresh test cases and new review packets.
