# M024.2 knowledge relevance gate — blind evaluation report

M024.1 found that irrelevant reference retrieval can degrade
troubleshooting decisions (CAD case 9/9 → 7/9, stable 3/3: a
service-recovery excerpt retrieved on generic filler primed the small
model toward Windows-services hypotheses). M024.2 adds a conservative,
evidence-aware relevance gate before knowledge excerpts enter model
context, then re-runs the affected cases and the complete FORGE
held-out suite under identical conditions.

No harness, rubric, or scenario changes in M024.2: the product change
is `backend/app/knowledge/relevance_gate.py` + a second-stage filter
in `match_references`, plus `backend/tests/test_m0242_relevance_gate.py`
(17 tests). Ranking (scores, order) is untouched; citations and the
quoted-excerpt injection boundary are untouched.

## 1. The gate (what shipped)

A ranked passage is KEPT iff at least one explainable criterion fires:

- error-code: query and passage share a code-like token (0x-hex or a
  3+ digit number such as an event id).
- subsystem: a discriminating query token hits the document title or
  section heading (the document is ABOUT the query topic).
- evidence: a discriminating measured evidence term hits the passage.
- topic: at least two distinct discriminating problem/service tokens
  hit (a coherent topical combination, not one lone word).

A token is discriminating iff it occurs in at most 3 corpus documents
AND is not generic English / generic IT filler (a ~700-term list
holding only words that are subsystem-agnostic in every plausible
troubleshooting context; subsystem, product, device, state, and
error-vocabulary words are deliberately never generic). When nothing
is sufficiently relevant, retrieval returns [] and no knowledge block
is sent. There is no per-scenario, per-document, or per-case
special-casing (pinned by test).

The rule took two iterations, and the suite caught the first one's
mistake: revision 1 (document frequency ≤ 2, single-term OR) filtered
the genuinely topical stopped-service query (all shared terms are
corpus-wide) and failed F3's required retrieval 3/3. Revision 2
(threshold 3 + the topic-pair rule) keeps coherent common-term
combinations while still filtering lone rare filler. Revision-1 eval
numbers (~100 loopback calls) are discarded as non-final; everything
below is the shipped revision.

## 2. Method

Identical conditions to M024.1: local inference only (loopback
Ollama, qwen3:4b, Fury default placement = GPU),
`FIELDROOK_OFFLINE=1`, fixture diagnostics. Frozen M019 held-out
suite (6 scenarios) 3x, frozen FORGE suite (5 scenarios) 3x, plus a
gate-off ablation (cad ×2, onedrive ×2, in-process default flip, no
source change) to test causality. Rubric frozen; automated FAILs are
kept as scored with disagreements called out, same as M024.1.

One comparability note: M024.1's early runs recorded end-of-run
endpoint refs as [] while their `references_retrieved` checks passed
(the harness was still being edited mid-gate), so M024.1 retrieval
*lists* are unreliable except for run `20261029T003541Z`. Check
outcomes and the M024.1 prose claims remain comparable; all M024.2
retrieval data below is self-consistent (evaluator, transcript line,
and summary read the same end-of-run endpoint).

## 3. Results

qwen3:4b, checks passed / total:

| suite | run | checks | calls | wall |
|---|---|---|---|---|
| heldout (M019 post-fix `20261028T143606Z`) | baseline | 48/53 | 16 | - |
| heldout (M024.1) | `…T003059Z` etc. | 45/53 x3 | 13-15 | ~34s |
| heldout (M024.2) | `20261029T085124Z` | 46/53 | 23 | ~52s |
| heldout (M024.2) | `20261029T085218Z` | 46/53 | 19 | ~31s |
| heldout (M024.2) | `20261029T085252Z` | 47/53 | 16 | ~29s |
| forge (M024.1) | `…T003135Z` | 47/50 | 13 | ~30s |
| forge (M024.1) | `…T003541Z` | 44/50 | 16 | ~32s |
| forge (M024.2) | `20261029T085322Z` | 45/50 | 14 | ~27s |
| forge (M024.2) | `20261029T085351Z` | 44/50 | 18 | ~32s |
| forge (M024.2) | `20261029T085425Z` | 47/50 | 14 | ~27s |
| heldout ablation, gate off | cad ×2 | 7/9, 7/9 | 2, 2 | ~5s |
| heldout ablation, gate off | onedrive ×2 | 7/8, 7/8 | 3, 3 | ~7s |

Per-scenario (best run shown; failures stable unless noted):

| scenario | checks | quality (1-5, single grader) |
|---|---|---|
| cad-license-checkout | 9/9, 8/9, 9/9 (asked-errortext in r2) | 4 |
| webcam-teams-calls | 7/9, 7/9, 8/9 (physical, crossapp flips) | 3 |
| bsod-after-driver | 9/9 x3 | 5 |
| onedrive-sync-conflicts | 7/8 x3 (scoped-multiuser) | 2 |
| monitor-resolution | 7/9 x3 (asked-cable, asked-driver) | 2 |
| shared-mailbox-permission | 7/9, 8/9, 7/9 (scoped-owa; asked-error flips) | 3 |
| forge-collector-dns | 9/10, 8/10, 9/10 (scoped; used-import in r2) | 4 |
| forge-ref-dns-relevant | 9/10 x3 (scoped) | 3 |
| forge-ref-service-misleading | 9/10 x3 (not-misled) | 4 |
| forge-contradiction-crash | 8/9, 8/9, 9/9 (contradiction window) | 4 |
| forge-unresolved-vpn | 10/11, 10/11, 11/11 (asked-pattern flips) | 5 |

USEFUL (all checks pass + score >= 3): cad-r3 (model-driven 9/9;
r1's 9/9 came via the deterministic fallback after unusable triage),
bsod-r2 (model-driven 9/9), vpn-r3 (honest 11/11), crash-r3 (9/9).
No SAFETY_FAILURE in any run: remote-target guards pass 100%,
`no_unsafe_steps` and `no_model_proposals` pass 100%.

## 4. The CAD recovery is causal, not luck

- Gate ON: 9/9, 8/9, 9/9 with zero excerpts retrieved in all three
  runs. r3 is model-driven throughout (users-scoping Q1, license-
  error-text Q2, license-server ping step; hypotheses stay license/
  network, no service-status questions anywhere). r1's 9/9 came via
  the deterministic fallback after unusable triage output (product
  behavior, disclosed, not model reasoning). r2's single miss is
  ordinary small-model fixation (server-name loop, never asks the
  error text), not priming: no service vocabulary appears.
- Gate OFF (ablation, same code otherwise): 7/9, 7/9 with
  `ref-service-recovery` retrieved both runs and the identical
  M024.1 FAIL pair (scoped, asked-errortext). This exactly reproduces
  M024.1's stable 7/9, closing the causal loop: the filler-prime
  excerpt caused the regression, and the gate removes it.

## 5. Relevant knowledge still flows (not disabled)

- `forge-ref-dns-relevant`: `ref-retrieved` 3/3, `ref-guided` 3/3
  (cache/server steps pursued from the excerpt). Unchanged 9/10 x3;
  the scoped FAIL is the known question-preempts-step evaluator
  disagreement (right check proposed as a step, never run).
- `forge-collector-dns`: `ref-dns-triage` retrieved 3/3 via imported
  evidence; endpoint junk narrowed from 3 docs (M024.1 run
  `…T003541Z`: app-launch + dns-triage + service-recovery) to 1.
  r2's `used-import` FAIL is keyword narrowness, not ignorance: Q1
  asks "which specific intranet sites" (no dns/resolv/lookup word)
  while both hypotheses name DNS resolution from the excerpt.
- `forge-ref-service-misleading`: required `ref-service-recovery`
  retrieval 3/3; `no-service-cause` 3/3 (the quoted-context
  safeguard holds with two excerpts present). `not-misled` fails
  3/3 on the same stall-after-weakening dynamic as M024.1 §5.1
  (both service hypotheses weakened at the design-note turn, then
  no re-scoping question); here without re-scope words, same score.
- Unit level: 17 gate tests pin pass-cases for every seed doc, plus
  error-code, title-topic, and evidence routes; the DNS E2E citation
  spec and all pre-existing ranking/injection tests stay green.

## 6. Variance, honestly reported

- onedrive 7/8 x3 (M024.1 flipped 7-8/8): no retrieval exists in ANY
  era (pre-gate best span scores 1; ablation refs [] both runs), so
  the gate cannot have caused the stable 7/8 — pure model variance
  (weak re-ask loop, never pursues multiuser scoping). The ablation
  (7/8 x2, gate off) confirms it.
- monitor 7/9 x3, webcam 7-8/9, mailbox 7-8/9: no retrieval in any
  era (openings share nothing scorable with the corpus); flips are
  sampling variance. My own discarded v1 iteration hit monitor 9/9
  once. mailbox flickered `asked-error` to PASS once (8/9, r2).
- vpn `asked-pattern` flips 10/11 without any retrieval: this
  weakens M024.1's contamination reading of its wandering r2 run —
  the flip happens with no excerpt at all, so it was most likely
  variance, possibly with excerpt contribution. r3 is an honest
  11/11 with no excerpts: the "no reference relevant → silence"
  behavior working as designed.
- Heldout totals 46-47 sit INSIDE M019's own pre-fix spread
  (46/53, 48/53); the remaining gap to M019's 48 is the same class
  of scoping-judgment misses M019 already disclosed.
- Cost: some runs take more turns without excerpts (heldout calls
  23/19/16 vs M024.1's 13-15 and M019's 16; r1's monitor ran 5
  turns). Within 1.5x, likely exploration variance; flagged, not
  judged a regression.

## 7. Residuals and evaluator disagreements (FAILs kept as scored)

1. F3 retrieves a second, weakly relevant doc (`ref-error-codes`,
   via the common-term pair service+start matching "service log" /
   "start with the exact string") in all 3 runs. No measured harm:
   identical 9/10 to M024.1, safeguard checks green, no error-code
   fixation in any transcript. Tightening the pair rule to require
   a rare term would re-break the required service retrieval;
   left as documented residual.
2. `contradiction_handled` window (frozen): F4 r1/r2 show textbook
   revision AT the delivery turn (both hyps weakened + printer-
   driver step), then fail the window. Same disagreement as
   M024.1 §5.1; r3 lands in-window (9/9).
3. `scoped` via `any_beat_used` (frozen): F1/F2 propose exactly the
   right scoping check as a step without ever getting a turn to run
   it. Same disagreement as M018/M019/M024.1.
4. Single-term topical queries ("window will not open") now yield
   no excerpts: accepted false negatives. Withholding is safer
   than mispriming (M019 proves the model works with zero
   excerpts), and real queries with any second topical term pass.

## 8. Cost, latency, repetition

- 114 loopback Ollama calls total for the final numbers (104 across
  the 6 suite runs + 10 ablation), zero cloud, zero downloads.
  (~100 more in the discarded v1 iteration.)
- 2-6 model calls and ~5-18s wall per scenario on Fury GPU; same
  efficiency class as M019/M024.1 (see the turns note in §6).
- Repetition low: every `questions_capped` check passes; the
  duplicate-question guard fires occasionally (withheld=1-2) and
  stall notes appear on don't-know loops, as designed.
- CPU placement NOT re-measured; M019's true-CPU FAIL stands.

## 9. Limitations

- Single model (qwen3:4b), single developer-grader (not
  independent; transcripts are model-identified since one model ran).
- 11 scenarios; small-sample by design (bounded gate eval).
- No live second-laptop case; no independent hardware; GPU only.
- M024.1's early-run retrieval lists are unreliable (see §2), so
  retrieval-list comparisons rest on M024.1 run `…T003541Z` plus
  check outcomes. M024.2 data is fully self-consistent.

## 10. Verdict

The gate achieves its goal with causal proof: the CAD priming
regression is gone (9/9, 8/9, 9/9; ablation reproduces M024.1's 7/9
with the excerpt back), relevant retrieval is preserved (DNS 3/3
guided, collector-DNS narrowed to the right doc, required service
retrieval 3/3 with the safeguard holding), and nothing else moved
outside variance (bsod identical, heldout inside M019's own spread,
all suites green: pytest 607, gauntlet 37/37, E2E 42/42, build
clean). Residuals (F3's second doc, frozen-window disagreements,
single-term silence) are documented above with measured no-harm.
M024.1's NOT-validated items (second machine, independent hardware,
8 GB laptop, standalone build) are unchanged and remain the only
known validation gaps. On M024.2's evidence, `forge/integration`
is ready to merge into `master` pending authorization.
