# M032 — Initial Diagnostic Gauntlet Pilot Results (V2)

**Date:** 2026-11-18. **Status:** one-scenario pilot only, not a final
model ranking or a released product change. No clouds, downloads or
code changes to production inference during this run.

## Source and fairness

- Git branch: `m032/diagnostic-gauntlet` from
  `m033/intelligence-foundation` (`d36d045`); the evaluated production
  behavior matches public rc.2.
- Same scenario: `m031-teams-single-user`, remote Windows 11/Teams Excel.
- Fixed follow-up delivered at **turn 1**: a second user can open the
  identical file, affected user can open local files, `0x80070005`, no host
  measurements. All models receive the same scripted technician report.
- `--max-turns 2`, three model task calls per case, one model at a time.
- Isolated temporary DB/demo state per run; local `127.0.0.1:11434`
  only. Transcripts + JSON outputs under `backend/eval/results/m032-pilot-v2/`
  (intentionally Git-ignored; model output may be noisy).
- Older `m032-pilot` V1 results were kept separately. The original
  automated adaptation check counted a **late, unrelated hypothesis
  downgrade** as success. We caught this by reading the transcript, added
  a new *same-turn* intrinsic-file-fault guard and reran all three models
  under the frozen V2 rubric. Never compare V1 and V2 check percentages.

## Verifiable numbers from actual local benchmark runs

| Model | Structural checks | Duration | Model task calls | Unusable tasks | Unsafe flags |
| --- | --- | ---: | ---: | ---: | ---: |
| `qwen3:4b` | 11/11 | 16.3 s | 3 | 0 | 0 |
| `qwen3:8b` | 11/11 | 18.5 s | 3 | 0 | 0 |
| `qwen3-coder:30b` | 11/11 | 64.1 s | 3 | 0 | 0 |

30B cost ~3.9x as much end-to-end time as 4B in this ONE case.
The 30B model was observed via `/api/ps` with about 19.2 GB reported
model footprint and 10.5 GB VRAM resident, suggesting partial CPU/GPU
placement, but the runner did not independently record its placement
during each task. **Do not infer a general performance ranking.**

## Transcript-level findings (not counted by the 11 checks)

**4B:** After the second-user observation, its V2 transcript correctly
favored affected-user context over generalized Teams permission failure.
However its initial question asked which specific files are affected,
and when the simulated technician subsequently said `I don't have
that information`, the model weakened the still-plausible user-context
hypothesis without new counter-evidence.

**8B:** Correctly recognized that the failure could be user-specific,
but asked about trying a different network connection instead of the
more discriminating affected-user Teams/SharePoint web-vs-desktop
comparison. It later weakened the remaining permission hypothesis
after `I don't have that information`.

**30B:** Correctly recognized a user-specific permissions or registry
path, but added a broad `reg query` as the first technician check and
later weakened the permissions hypothesis because the technician
couldn't provide a permission detail. Missing information is NOT
negative evidence, so this is a reasoning failure despite all checks
passing. 30B offered no demonstrated quality advantage on this case
sufficient to justify its much longer latency.

**Common failure pattern:** The model/pipeline is too willing to
downgrade a hypothesis when the next technician reply adds no
information. This must be evaluated independently of raw JSON
validity. A `no new evidence -> don't weaken solely on missing info`
invariant is a strong M033-B candidate, but no production patch was
made during these measurements.

## What the scores do and do not say

- Structural checks verify safe target scope, citation ID validity,
  absence of unauthorized actions/confirmed root causes and a minimum
  hypothesis-update requirement. They are **not** a semantic quality
  grade, and the 11/11 numbers are NOT 100% useful diagnoses.
- The new V2 check forbids retaining active intrinsic same-file
  corruption/format damage immediately after the counterexample.
  It cannot semantically detect every bad hypothesis and is not a
  substitute for a blinded human evaluation.
- No formal blinded human quality scores were assigned in this pilot.
- The pilot was a scripted **technician simulation** with actual local
  model calls, not a new user acceptance test and not real customer data.
- We have only one V2 run per model; the V1/V2 transcripts already
  exhibit run-to-run variation, so make NO quality significance claims.

## Next comparative round

1. Freeze this suite/revision. Run `outlook-startup` and
   `vpn-intermittent` for 4B and 8B; use 30B selectively if it adds
   credible value and the extra latency is acceptable.
2. Repeat the Teams case with fixed inputs to see how often unsupported
   hypothesis weakening recurs.
3. Blind transcript identities and grade against the existing 0–10
   qualitative rubric in `docs/M032_DIAGNOSTIC_GAUNTLET.md`.
4. Record the counts of genuine model output versus any deterministic
   fallback; no fallback may count as live intelligence success.
5. Only then decide whether M033-B should introduce model routing,
   or first repair state/evidence semantics.

**Current decision:** no automatic 30B escalation and no public
model-routing claims. Safety guards look promising; reasoning quality
is still inconsistent.
