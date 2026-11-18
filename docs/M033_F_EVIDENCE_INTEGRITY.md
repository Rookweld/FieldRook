# M033-F — Evidence Integrity / Source-Claim Audit

**Working branch:** `m033/fact-provenance` (forked from M033-E `789d97d`).
**Date:** 2026-11-18
**Status:** local development only. Not shipped in `v0.6.0-rc.2`.

## Why this milestone exists

M033-E's locked blind AI review identified three concrete reliability bugs
in real local Qwen3 model transcripts:

1. Camera failure in Teams and Windows Camera **on one laptop** was
   described as confirmed across **multiple devices**.
2. A timed-out `ping` to a licensing server was used to claim that the
   licensing service or network configuration **must be faulty**.
3. A newly installed network driver coinciding with blue screens was
   treated as grounds to **weaken a driver-conflict hypothesis**.

All three make diagnostic progress appear more certain than the available
observations justify. A language model's fluent conclusion is not a measured
fact. The existing M033-B deterministic rule already handles unavailable
information, but substantive (yet contradictory) conclusions needed
a separate, traceable audit.

## Implemented boundary

`backend/app/analysis/evidence_integrity.py` provides a **pure,
non-mutating** consistency review:

- Distinguishes technician reports from successful host readings, failed
  tools and other non-host artifacts. Only tool-backed, non-error readings
  are counted as host observations. This does not establish their
  *relevance* to an arbitrary root-cause claim.
- Flags a model's categorical **multi-host assertion** when the report
  does not establish distinct machines. Two applications on one computer
  must not become two devices.
- Flags a categorical **service/root-cause assertion based on failed
  ICMP** without appropriate independent support. Fresh generic OS
  readings cannot turn a `ping` into an application service check.
  A service-specific measurement may partly support a service-status
  claim, but never alone justifies a separate network-causality claim.
- Flags a questionable **hypothesis weakening after a newly reported
  technical change** involving the same salient component. A driver
  installation is not proof of driver failure; neither is it evidence
  *against* a driver problem. The guard requests review, not a
  predetermined verdict.
- Uses only fixed diagnostic signal names in activity details;
  doesn't copy user-provided text, account paths or screenshots into
  the audit note. No extra model call or data persistence.
- Has conservative hedging and explicit-negative exceptions to reduce
  false positives. A missed flag is not a safety guarantee.

`backend/app/analysis/loop.py` calls the audit on local-model
follow-ups after the existing M033-B no-information guard. The outcome
is recorded as an `Evidence integrity review` note only if a potential
mismatch is found. The existing `FIELDROOK_INFO_GAIN_MODE=off`
bypasses this experimental audit; `observe` (default) records
advisories without changing output. **Even `enforce` does not
rewrite hypotheses from M033-F:** that would require semantic validation
we have not established.

## Verification and known-case replay

- New unit tests cover three known cases, report/measurement provenance,
  malformed JSON-like model data, privacy-safe notes, negative controls,
  and cases where technical measurements are unrelated to the claim.
- Real local pipeline tests verify that the M033-F activity note
  is emitted, the model response is not rewritten, `off` skips the
  audit, and no extra inference task is performed.
- A **known-case replay** was executed offline using statements copied
  from the frozen M033-D transcripts. All three expected flags were
  observed and written to:
  `backend/eval/results/m033f_known_case_replay.json`.
  These are **not unseen generalization cases**, and the replay does
  not measure diagnostic accuracy or future false positive rate.
- Existing M033-C/M033-E ranker behavior and M033-B's hard
  no-information protection remain unchanged.
- Focused final-source evidence/agent tests: **80 passed** (exit 0).
  Offline known-case replay: **3/3 flagged** exactly the previously
  observed failure classes, no Ollama inference.
- A real `qwen3:4b` heldout local-model run completed 3/3
  scenarios with **23/27 structural checks** and no unusable
  responses. No integrity finding appeared in these particular
  fresh outputs; this is not proof that the audit is generally
  comprehensive, nor a model-quality gain.
- Two full-suite runs on Fury each passed **868 tests**, skipped 4
  and failed 1 in a *different* pre-existing demo-worker timing test.
  The failing status was not caused by the M033-F module. An isolated
  original recovery-lifecycle test had passed.
- The demo-worker **test harness only** has been improved to poll
  the atomic heartbeat in its unique pytest temporary directory,
  rather than repeatedly launching slow WMI identity probes. It
  correctly accepts the worker child PID rather than assuming the
  Windows virtualenv launcher and child interpreter use the same
  PID. The production worker, approval and verification code was
  **not changed**. After this correction, the full
  `tests/test_actions.py` suite passed **25/25**, exit 0.
- **Final complete backend verification after the Windows test-harness
  correction:** `pytest -q -p no:cacheprovider` completed on Fury:
  **869 passed, 4 skipped, 0 failed, 2 warnings**, 332.45 s,
  **exit code 0**. This is the release-gate-quality regression
  result for this development branch (not a new packaged release).
- The separate complete corrective-action suite also passed
  **25/25** after fixing the test harness. The existing runtime
  action, approval and postcondition verification code was not changed.
- The earlier two 868-pass/1-fail full runs and the temporary
  incorrect PID assertion were investigated, not silently dropped
  from the historical record.

## Explicit limitations

- Word-pattern findings are conservative **heuristics**, not verified
  natural-language entailment. The system cannot prove the correct
  root cause or classify every meaningful contradiction.
- A host-level measurement might concern a different target, source
  or time; the current counters do not establish cross-host identity
  or relevance by themselves.
- A driver-change overlap is merely a reason to check an inference;
  it does not automatically strengthen or weaken the hypothesis.
- The live/meta model pipeline and rc.2 release were not modified.
- No independent human review or new head-to-head model-quality
  improvement has been established.
- The next serious step is a structured, source-cited hypothesis
  transition proposal requiring linked evidence IDs and a technician
  verification gate, evaluated with blinded new cases before any
  automatic hypothesis suppression.
