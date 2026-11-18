# M033-B — Hypothesis Integrity Guard

**Review date:** 2026-11-18
**Working branch:** `m033/hypothesis-integrity` (forked from M032 baseline at `0474871`).
**Status:** local development; NOT part of the published v0.6.0-rc.2.

## Problem: missing information was treated as disproof

M031's real technician trial and M032's controlled local-model
comparisons exposed the same failure across 4B/8B/30B:

> The technician said "I don't have that information." The model then
> marked existing hypotheses weakened, even though the response supplied
> no measured or reported fact contradicting them.

M032 preserved the baseline transcripts:
`backend/eval/results/m032-pilot-v2/`,
`backend/eval/results/m032-expanded/`, and
`backend/eval/results/m032-repeats/`. See
[expanded results](M032_EXPANDED_RESULTS.md). The M032 baseline remains
committed on its own branch and must not be rewritten.

## Scope of the fix

- `backend/app/analysis/local_tasks.py`: stronger reassessment instruction:
  unknown or unavailable information **is not negative evidence**.
  Added a pure function to normalize a local model's proposed
  `weakened` transitions and verdict when that rule applies,
  retaining its proposed *next safe check/question* without mutating
  the source model response.
- `backend/app/analysis/loop.py`: deterministic safety check after
  local `reassess`, before assembling/merging the assessment.
  It uses the existing narrow no-information detector from
  `app.analysis.assist` (rather than introducing a competing
  classifier). A purely uninformative answer cannot downgrade
  hypotheses unless **newly collected tool-backed host evidence**
  or a **new, actually provided vision-capable screenshot** is present.
  The case activity log shows a `Hypothesis integrity guard` note.
  An attempted invalid downgrade also adds a warning.
- Follow-up screenshot delivery: for a consenting technician and a
  vision-capable local provider, the current-turn screenshot is now
  included in the local reassessment task. Historical screenshots
  are not resent as if they were freshly supplied. Models without
  vision never receive the image bytes.
- `backend/tests/test_local_tasks.py`: tests for absent facts,
  informative counterevidence, hedged but substantive replies,
  image/model capability boundary, fresh host measurements,
  raw-model-response preservation and no historical image resend.

## Boundaries we intentionally retain

- No router that silently switches between 4B, 8B and 30B.
- No autonomous remediation, shell access or host diagnostics
  on another computer; the existing consent and target policy remain.
- No false claim that a screenshot metadata record is a completed
  vision analysis. Real image bytes must actually reach a
  vision-capable task for the guard to allow evidence-based revision.
- `weakened` may still be output when a *substantive* new observation
  contradicts a hypothesis, even if the information came from a
  technician rather than an independent measurement.
- The detector is deliberately narrow: an arbitrary new sentence
  with no actual information may not always be recognized. That
  requires additional evidence-aware semantic validation, not a
  blanket ban on all model transitions.
- Only local-model reassessment path changed. Meta, deterministic
  simulation and earlier releases remain unchanged.

## Live comparison (illustrative, NOT a controlled causal estimate)

All calls used local Ollama. One post-change three-case run per model,
on exactly the same M032 scenario *definitions*, but model generation
varies and the M033 prompt changed:

| Model | Teams | Outlook | VPN |
| --- | --- | --- | --- |
| qwen3:4b | 11/11 (12.9 s) | 6/7 (5.0 s) | 7/7 (5.4 s) |
| qwen3:8b | 10/11 (17.2 s) | 6/7 (8.4 s) | 6/7 (8.3 s) |

The score variation means **we cannot claim overall superior AI
quality**. Crucially, in these transcripts hypotheses remained
unchanged after thin technician replies, while substantive technician
information still led to revisions. This matches the new deterministic
behavior checks. Real local-model outputs were produced (no simulated
fallback was counted as a model success).

## Acceptance requirements

1. Focused M033-B integrity tests must pass with the isolated Python 3.12
   interpreter (nine targeted tests).
2. Full backend suite must pass; compare with the original 755-pass
   M033-A baseline plus M032 and M033-B tests.
3. No unintended frontend or native shell changes; published rc.2 and
   `master` remain untouched.
4. `git diff --check` and Python compilation must pass.
5. Retain all raw pre/post benchmarks under Git-ignored result paths
   for later review. Do not mistake 11/11 checks for 100% sound diagnosis.
6. Commit only reviewed files on `m033/hypothesis-integrity`;
   no push, merge, tag, or distribution without a separate release review.

## Subsequent engineering candidate

The next qualitative failure remains **diagnostic question selection**:
in both model sizes the Outlook case often missed the safe-mode
or onset/recent-change branch, and 8B occasionally wandered to a
less discriminating networking question in the Teams case. This is
worth an M033-C/M034 "Information Gain" milestone only after we have
repeatable scoring and a human-blinded review.

The diagnostic system should optimize *useful evidence gained per
safe step*, not how confidently or quickly a model speaks.
