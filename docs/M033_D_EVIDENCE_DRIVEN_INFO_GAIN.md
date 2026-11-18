# M033-D — Evidence-Driven Information Gain

**Development milestone — 2026-11-18.** Branch: m033/evidence-driven-information-gain, forked from M033-C at 187adf3. No production inference behavior, model router, permissions, WPF UI, or published v0.6.0-rc.2 artifacts were modified.

## What we learned from M033-C

The original A/B evaluation on three heldout cases showed:
- Qwen3:4B: M033-B 25/27 versus M033-C experiment 23/27 structural checks.
- Qwen3:8B: M033-B 26/27 versus M033-C experiment 25/27 structural checks.

These are only one run per model/version; NOT proof of a general regression, nor evidence that a model is more intelligent. The observed lack of improvement is why M033-C defaults to observe and does not change the next diagnostic step.

The new question for M033-D is more demanding: **Does the proposed technician action distinguish plausible causes through actually different, observable answers?** A confident or contrast-heavy sentence alone is insufficient.

## Implemented M033-D deliverables

1. backend/eval/m033d_review.py — deterministic, read-only review generator and human-score validator. Uses *already recorded* local Ollama challenge transcripts; no API calls, model downloads, inference, filesystem changes outside the specified output destination, or customer information.
2. backend/eval/m033d_html.py — generator for a self-contained, offline HTML reviewer. No CDN, external scripts, remote endpoints, telemetry or model context forwarding.
3. backend/tests/test_m033d_review.py — tests for pairing, schema, sanitization, unblinding boundary, overlaid edits, duplicate/missing/mismatched cases, strict 0–max integer scoring, human rationale requirement and standalone offline HTML.
4. A generated 6-pair, 12-transcript review pack under backend/eval/results/m033d-first-blind/ (intentionally excluded from Git). The 6 pairs compare the same scenario and model, but the labels are hidden. Three cases: CAD license checkout, black webcam in Teams, and blue-screen after driver changes. The previous raw benchmarks are preserved.

### Review questions and counterfactual outcomes

Each case supplies two possible *interpretations* of a safe diagnostic observation, rather than a list of required question keywords.

- CAD: if several engineers fail, inspect shared licensing/network infrastructure; if only one fails, inspect client settings/account path.
- Teams camera: if Windows Camera fails too, inspect hardware/device/privacy/driver; if only Teams fails, inspect app permissions/configuration.
- Blue screen: if safe mode is stable, investigate additional drivers/services; if it also fails, broaden the investigation.

These are plausible branches, not proven root causes. Alternative safe discriminating checks may score just as highly.

### Human rubric (10 points total)

- Discrimination, 0–3: Does the next question/check separate two meaningful hypotheses by observable results?
- Fidelity, 0–3: Does it preserve the difference between reported facts, actual measurements, and unknowns?
- Actionability, 0–2: Is it safe, concrete and feasible for a technician?
- Calibration, 0–2: Does it avoid false certainty and unjustified hypothesis downgrades?

**These are human grades only.** Automated safety/structural checks remain separate. The review tool cannot and does not manufacture a "quality score" for the model.

## Exact First Contact for the human reviewer

On Fury, open the file below in Chrome or Edge by double-clicking it:

C:\dev\FieldRook_EvidenceTrials\backend\eval\results\m033d-first-blind\review\REVIEW_OFFLINE.html

The page shows both anonymized candidate transcripts side by side and records four rubric scores plus a short human rationale. Review the *first recommended diagnostic direction*, read later turns for calibration, and grade each candidate independently. Do not try to guess which variant or model it is.

When finished:

1. Click **Export scores.json**. If interrupted, export a partial score file and later use **Import scores.json** to resume locally; the page does not silently store ratings in a cloud account.
2. Save/replace the exported scores.json under:
   C:\dev\FieldRook_EvidenceTrials\backend\eval\results\m033d-first-blind\review\scores.json
3. Run the validator in PowerShell:

   cd C:\dev\FieldRook_EvidenceTrials\backend
   .\.venv\Scripts\python.exe -m eval.m033d_review evaluate --output eval\results\m033d-first-blind

4. The validator rejects missing ratings, bool/float values instead of rubric integers, missing human rationales, changed transcript text, altered schema/identity lists, and duplicate/unrequested reports. Only after all 12 grades are valid does it write the private unblinded output:
   backend/eval/results/m033d-first-blind/private/HUMAN_RESULTS.json

**Never open the private answer key before completing all twelve ratings.** The packet suppresses model identity, mode hints, latency and old pass/fail grades, although style differences might still provide imperfect indirect clues. Only one human reviewer so far is available and we make no statistical-quality claim.

## Verification performed

- 6 actual paired cases, 12 anonymous transcripts, prepared successfully on Fury (exit 0).
- A deliberate attempt to evaluate an unrated pack returned exit 2 and no unblinded results.
- A real Playwright/Chromium smoke test on Fury verified exactly 6 case sections, 12 cards, 48 rubric selectors, progress reporting, score export **and import after a browser reload**, no runtime JS errors and zero external requests (exit 0). Synthetic test scores were never written into the real review pack.
- 16 focused unit tests passed, including a real offline HTML generator test. Full backend regression: **831 passed, 4 skipped, 0 failed**, 2 previously known warnings, exit code 0, 378.68 seconds (Python 3.12). No human grades have been entered or invented.

## Next gate — NOT done automatically

When a human technician has completed the blind review, compare per-case paired model results **without cherry-picking**. If experiment mode improves useful differential questions but harms safety or evidence fidelity, do NOT enable it. If the experimental mode does not improve results, investigate why the candidate ranking misfires; retain M033-C observe by default.

Only after a successful, repeated and reviewed outcome should M033-E consider production information-gain selection changes. Prioritize information obtained safely per technician effort rather than higher model size or prettier prose.
