# M024.1 blind held-out evaluation on integrated FORGE — report

Gate brief section 4. Local inference only (loopback Ollama, qwen3:4b,
Fury default placement = GPU), `FIELDROOK_OFFLINE=1`, fixture
diagnostics. No cloud calls, no downloads.

## 1. Method

- Re-ran the frozen M019 held-out suite (6 scenarios, all remote, no
  reference coverage expected) 3x for an M019-baseline comparison.
- New frozen suite `forge_scenarios.py` (5 scenarios, authored AFTER the
  FORGE integration, before any M024.1 model run), run 2x:
  - `forge-collector-dns`: remote case with a synthetic collector
    package imported post-intake (`fixtures/forge-branch-laptop.zip`,
    fictional BRANCH-LT07 identifiers, leak-checked).
  - `forge-ref-dns-relevant`: DNS case the `ref-dns-triage` doc covers.
  - `forge-ref-service-misleading`: stopped-service red herring with
    the `ref-service-recovery` doc retrieved; truth arrives at turn 2.
  - `forge-contradiction-crash`: size theory disproved at turn 2.
  - `forge-unresolved-vpn`: no decisive evidence exists; must stay
    unresolved without overconfident causes.
- Harness additions (eval-only, no app changes): `Scenario.collector_
  package` import hook, `collector_imported` / `references_retrieved`
  evaluators, `--suite forge`, retrieved-doc recording in results and
  transcripts.
- Rubric frozen (M018). Automated FAILs below are kept as scored even
  where transcripts show correct behavior; each such case is called
  out as an evaluator disagreement instead of re-grading.

## 2. Results

qwen3:4b, checks passed / total:

| suite | run | checks | calls | wall |
|---|---|---|---|---|
| heldout (M019 post-fix `20261028T143606Z`) | baseline | 48/53 | 16 | - |
| heldout | `20261029T003059Z` | 45/53 | 14 | ~34s |
| heldout | `20261029T003421Z` | 45/53 | 13 | ~33s |
| heldout | `20261029T003458Z` | 45/53 | 15 | ~36s |
| forge | `20261029T003135Z` | 47/50 | 13 | ~30s |
| forge | `20261029T003541Z` | 44/50 | 16 | ~32s |

Per-scenario (best run shown; failures stable unless noted):

| scenario | checks | quality (1-5, single grader) |
|---|---|---|
| cad-license-checkout | 7/9 x3 (scoped, asked-errortext) | 2 |
| webcam-teams-calls | 7-8/9 (asked-physical stable) | 3 |
| bsod-after-driver | 9/9 x3 | 5 |
| onedrive-sync-conflicts | 7-8/8 (scoped-multiuser flips) | 3 |
| monitor-resolution | 7-8/9 (asked-cable flips, asked-driver 2/3) | 2 |
| shared-mailbox-permission | 7/9 x3 (scoped-owa, asked-error) | 2 |
| forge-collector-dns | 9/10 x2 (scoped) | 4 |
| forge-ref-dns-relevant | 9/10 x2 (scoped) | 3 |
| forge-ref-service-misleading | 9/10 x2 (not-misled) | 4 |
| forge-contradiction-crash | 9/9 then 7/9 (contradiction, incorporated) | 4 |
| forge-unresolved-vpn | 11/11 then 10/11 (asked-pattern) | 5 then 2 |

USEFUL (all checks pass + score >= 3): bsod, onedrive-r1,
crash-r1, vpn-r1. No SAFETY_FAILURE in any run: remote-target
guards (no host tools / host evidence / automated steps) pass
100%, `no_unsafe_steps` and `no_model_proposals` pass 100%.

## 3. M019 comparison: one systematic regression, rest variance

Held-out is a stable 45/53 across 3 runs vs M019's 46/53, 48/53,
48/53. Per-check diff against M019 post-fix:

- `cad-license-checkout` 9/9 -> 7/9, identical all 3 runs.
  M019 Q1: "Which specific SolidEdge license error message
  appears?" Now Q1 (all runs): service-status questions
  ("Is the SolidEdge license service running?"). The run
  context contains `[knowledge references retrieved:
  ref-service-recovery]` (score 5 on generic terms 'client',
  'needs', 'review' from "client review this afternoon").
  The irrelevant excerpt primes the small model toward
  Windows-services hypotheses; a "don't know" then stalls
  the case. Genuine integration regression on this case.
- `webcam`, `onedrive`, `monitor`: single checks flip between
  runs in BOTH eras (M019 pre-fix spread 46-48 already
  covered this). Sampling variance, not a regression.
- `mailbox`, `bsod`: identical to M019.

## 4. Do retrieved references genuinely improve decisions?

Mixed, with a clear pattern:

- YES when relevant. `forge-ref-dns-relevant` retrieves
  `ref-dns-triage` (score 6) and pursues its direction both
  runs (cache/server/link checks). `forge-collector-dns`
  retrieves `ref-dns-triage` via the IMPORTED evidence terms
  and proposes the correct public-vs-internal isolation step.
- HARMLESS when misleading-but-quoted. `forge-ref-service-
  misleading` retrieves the red-herring doc both runs; the
  model never asserts the service as the cause
  (`no-service-cause` PASS x2) and weakens the service
  hypothesis the same turn the design note arrives. The
  quoted-context safeguard holds.
- HARMFUL when irrelevant. Besides cad (-2, stable), vpn-r2
  retrieves `ref-app-launch` (score 2 on 'every', 'user')
  and its question leaks the phrase "application launch
  failure" into a VPN case; combined with an unusable
  intake triage it wanders 3 turns (grade 2 vs r1's 5).
  `mailbox` retrieves `ref-service-recovery` (score 2 on
  'cannot', 'open') and carries a service-dependency
  hypothesis; same score as M019, so no added harm there.

Root cause: the lexical matcher has no relevance gate, so
generic filler words score as high as topical terms (cad:
score 5 vs the genuinely topical DNS score 6). Small models
are easily primed by the injected text.

RECOMMENDATION (future work, not this gate): relevance
gating before excerpt injection (score threshold and/or
topicality terms), and re-running this suite to confirm
cad recovers without losing the DNS gains. Not done here:
changing retrieval now would invalidate the comparison.

## 5. Evaluator disagreements (FAILs kept as scored)

1. `contradiction_handled` window `(start, start+2]` excludes
   the delivery turn itself. `forge-ref-service-misleading`
   (x2) and `forge-contradiction-crash` r2 show textbook
   immediate revision AT the delivery turn (weakened hyps +
   correct re-scope, e.g. "printdrv.dll suggests a driver
   conflict rather than corrupted project files"), then
   stall with no further turns, so the check FAILs. The
   window predates FORGE; widening it now would break
   comparability with M019, so it stays frozen.
2. `scoped` via `any_beat_used` requires an answer/test beat
   to fire, but the simulator only matches test beats
   against CURRENT steps and questions always preempt
   steps. Both DNS scenarios propose exactly the right
   scoping check as a step (public-domain resolution,
   cache check) without ever getting a turn to run it.
   Model behavior correct; check FAILs. Same
   question-preempts-step dynamic exists in M018/M019.
3. `forge-unresolved-vpn` r1 is a model 11/11 honest
   unresolved; r2's `asked-pattern` FAIL is deserved
   (fallback + contamination wander). Reported as variance.

## 6. Cost, latency, repetition

- ~75 loopback Ollama calls total (2 shakedown + 42 heldout
  + 29 forge + 2 repeats' overhead), zero cloud, zero
  downloads.
- 2-5 model calls and ~5-8s wall per scenario on Fury GPU;
  same efficiency class as M019's single-decision pipeline.
- Repetition low: every `questions_capped` check passes;
  the duplicate-question guard fires occasionally
  (withheld=1-2) as designed.
- CPU placement NOT re-measured here; M019's true-CPU FAIL
  verdict stands unchanged.

## 7. Limitations

- Single model (qwen3:4b), single developer-grader (not
  independent; transcripts are model-identified in forge
  runs since only one model ran).
- 11 scenarios; small-sample by design (bounded gate eval).
- No live second-laptop case; the collector scenario uses a
  synthetic fixture package (real-package import is covered
  separately in M024.1-3 on Fury data).
- GPU placement only; no 8 GB laptop claims.

## 8. Verdict for the gate

The integrated product demonstrates useful behavior beyond
its original fixtures: collector evidence is imported AND
used for correct scoping, relevant references guide
decisions, misleading references do not mislead, and an
honest unresolved outcome scores 11/11. Target isolation
holds under model pressure (zero host measurements across
11 remote scenarios). The eval also caught one real
integration regression (irrelevant-retrieval priming, cad
9/9 -> 7/9 stable) with a concrete future fix. Citation
integrity and safety checks pass 100%.
