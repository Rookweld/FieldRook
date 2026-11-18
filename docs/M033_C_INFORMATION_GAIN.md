# M033-C — Information Gain / The Next Best Diagnostic Move

**2026-11-18 · Working branch:** `m033/information-gain`
**Parent:** `m033/hypothesis-integrity` at `351ec30`.
**Status:** local development candidate, not included in published
`v0.6.0-rc.2`; no push, merge, Windows packaging or tag authorized.

**Verified on Fury (2026-11-18):** 815 passed, 4 skipped,
0 failed; full backend `pytest -q -p no:cacheprovider` exit code 0
(380.43 s, 2 known warnings). 108 focused M033-C/integrity/
guidance tests passed. Python compilation and `git diff --check`
passed. Default/observe prompt parity against the untouched
M033-B control was checked for four distinct input combinations,
with exact string equality in all four cases.

## Experiment modes (default is deliberately non-interfering)

`FIELDROOK_INFO_GAIN_MODE` has three explicit settings:

- `off` — M033-B model prompts and normal decisions; no M033-C
  review, alteration or activity entry.
- `observe` **(default)** — M033-B prompts and original model
  decisions remain unchanged. The M033-C reviewer is run in
  shadow mode; only a clearly labeled `Would select ...` note is
  appended to the activity log. No content is changed or blocked.
- `enforce` **(experimental opt-in)** — use M033-C prompt
  guidance and apply ranked question/check choice and safety/
  reported-code integrity checks before assessment assembly.
  Only this mode can change the model's proposed next move.

Invalid mode values fall back to `observe`. The single-decision
pipeline still makes no extra AI calls in any mode. Use
`--info-gain-mode observe|off|enforce` with the local challenge
runner; summary JSON records the chosen mode. Because `observe`
uses exactly the M033-B prompt text, changing the default cannot
silently alter routine diagnosis choices. A separate parity audit
compared multiple remote/local triage and reassessment prompts
(including thin answers and reference context) against the untouched
M033-B control worktree: all text matched exactly.

**Important:** The guidance safety classifier has also gained an
independent correction for verb-first registry edits. Unlike the
experimental ranking, that safety classification applies normally.

## Objective and acceptance standard

Choose a **useful, safe next diagnostic question or technician check** instead
of repeatedly requesting vague details. A higher score or more fluent answer
does NOT prove a more accurate diagnosis. Preserve M033-B's rule that a
technician's `I don't know` cannot independently weaken hypotheses.

M032 established a specific baseline problem: both Qwen3:4B and Qwen3:8B
frequently missed a discriminating Outlook check, and sometimes weakened
hypotheses despite receiving no new evidence. Those original reports and
model transcripts remain untouched under `backend/eval/results/`.

## Implemented architecture

The local one-call-per-round triage/reassess architecture remains unchanged.
**In `enforce` mode only**, revised model prompts prioritize:
- The **last successful observable step** vs **first failing step**; or
- The same user action under **one safely changed condition**; and
- Explicitly why different outcomes would lead to different diagnostic
  interpretations, rather than repeated generic "scope" interviews.

`app/analysis/information_gain.py` is a bounded, pure deterministic reviewer:
- Scores only *model-authored* question candidates and next checks using
  observable language features (contrast, specificity, stated decision
  impact, relation to open hypotheses), repeat detection and known-fact
  penalties. The score is an **unvalidated heuristic proxy**, NOT Shannon
  information gain, confidence or a measure of AI correctness.
- Where a model offers an optional second safe question, prefers it only
  when materially better (otherwise preserves the first).
- Compares a low-value question with an actually safer, concrete
  *model-proposed technician check*. A distinctly better check can go first;
  the engine does not invent content or trigger any extra inference call.
- An unsafe/privileged/system-changing question or proposed check cannot
  silently receive "safe manual" treatment. The shared guidance filter now
  correctly recognizes verb-first registry modification phrases (for
  example, "edit the registry").
- Detects when a model changes a known, explicitly reported hexadecimal
  error code while formulating a question or check. Conflicting proposals
  are suppressed, **not rewritten as if they were measured**.
- Does not drop a technically plausible check merely because this
  heuristic fails to classify its format (such as a read-only CLI command).
- Decisions use no external services, store no secret prompt content,
  and run in constant bounded work per proposed candidate.

`app/analysis/loop.py` optionally reviews questions after local-model
calls, before assessment assembly and merge. In default `observe`,
it does **not** apply the review to the assessment; the activity log
says what it *would* select, with a proxy score explicitly labeled
**not diagnostic proof**. In `enforce`, it applies the proposed
ranked choice. In `off`, it skips the reviewer entirely. No extra
model calls, autonomy, remote host measurements or tool permissions
were introduced.

`app/analysis/local_tasks.py` leaves the existing JSON contract intact,
and does not force weaker models to output additional candidate fields.
When a valid safe check already supplies the next step, the assembler
does **not** manufacture two generic fallback questions.

## Safety and limitations

- Read-only scope stays enforced by the underlying target/tool registry;
  the reviewer is an additional **selection/filtering layer**, not a
  permission system.
- A high proxy score **cannot prove** that the suggested check exists,
  that a root cause is likely, or that the wording is meaningful.
  Hallucinated Windows services, poor comparisons, irrelevant checks
  and incorrect hypotheses remain possible.
- The fixed error-code guard currently compares explicit `0x...`
  codes in the problem report with proposed next-move wording; it is
  not a semantic verifier of all facts or collector observations.
- An unknown answer does not become negative evidence: M033-B's
  deterministic guard remains active and covered by regression tests.
- Any case-level structural check is distinct from **human-blinded
  transcript quality**. Do not claim the local model is "9/10 good"
  because a heuristic scores one sentence 9/10.

## Reproducible test plan

- Tests: `backend/tests/test_information_gain.py`,
  `backend/tests/test_local_tasks.py`,
  `backend/tests/test_guidance.py`,
  `backend/tests/test_m032_gauntlet.py`.
- M032 original three-case suite: `m031-teams-single-user`,
  `outlook-startup`, `vpn-intermittent`; 4B and 8B local Ollama.
- Independent generalization scenarios (not used to design the
  prompts): `cad-license-checkout`, `webcam-teams-calls`,
  `bsod-after-driver` in the existing heldout suite.
- Grounded control: `351ec30` (M033-B) checked out in a **separate
  detached worktree**; same virtualenv, local Ollama and frozen scenarios.
  Sequential model runs avoid competing GPU activity. Single runs
  cannot establish statistical significance.
- Store raw JSON summaries and readable transcripts in git-ignored
  `backend/eval/results/m033c-*` and retain earlier
  `m032-*` baseline directories.

## Pilot progression (do not cherry-pick one lucky run)

| Stage | 4B M032 three-case checks | 8B M032 checks | Interpretation |
| --- | --- | --- | --- |
| Prior M033-B example | 24/25 | 22/25 | One historic sample per model |
| M033-C V1, long optional-candidate prompt | 23/25 | 23/25 | No meaningful gain; 4B produced invalid JSON in Outlook |
| M033-C V2, shorter decision prompt | 23/25 | 23/25 | No meaningful gain; 4B still occasionally produced unusable Outlook JSON |
| M033-C V3, clearer failure boundary | 24/25 | 23/25 | Outlook 4B passed once; other quality failures remain |

A direct diagnostic with 4B and the Outlook prompt produced valid
JSON under **both** output budgets of 220 and 340 tokens, so a fixed
token-limit explanation for occasional invalid JSON is **not proven**.
The model sometimes also changed reported code `0x80070005` to
`0x80070105`, which motivated the generic evidence-consistency guard.

### Separate M033-B control against previously unseen cases

Both control and experimental variants used the same local Ollama,
six runs (three heldout cases for each of 4B and 8B), isolated
investigation databases, and the same existing hidden checks:

| Heldout results | Qwen3:4B | Qwen3:8B |
| --- | ---: | ---: |
| M033-B control (unchanged `351ec30`) | 25/27 | 26/27 |
| M033-C experiment (enforce, pre-mode code) | 23/27 | 25/27 |

**No proven quality gain.** These are one-run-per-model/version observations,
not statistical estimates or blinded human reasoning-quality ratings.
The control run consistently did as well or better on raw structural
checks. This is why new code defaults to `observe`, not `enforce`.

The final code is not claimed to be "more intelligent" until repeated
diagnostic quality gains are demonstrated, not just guard tests.

## Next step after M033-C

M033-D candidate: **Evidence-Driven Information Gain**, with explicit
expected observations, a human-rated next-check quality rubric, and
real technician review of question usefulness. Keep it separate from
routing larger models or expanding autonomous actions.
