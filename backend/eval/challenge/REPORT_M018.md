# M018 unknown-problem challenge — report

Date: 2026-10-28. Host: Fury (i7-13850HX, 68.4GB RAM, RTX 3500 Ada 12GB).
Challenge code: `backend/eval/challenge/` (rubric, 20 scenarios, technician
simulator, runner). Raw transcripts + summaries: git-ignored
`eval/results/challenge/<stamp>/`; this file is the committed record.

## 0. The GPU correction (read first)

M017 reported "CPU-only" numbers. That was wrong: Ollama silently used
Fury's RTX 3500 Ada for every M017 measurement (`ollama ps`: 100% GPU).
Consequences:

- M017 absolute speeds are GPU-flavored: qwen3:4b triage ~2.5s warm at
  ~90 tok/s (GPU) vs ~25-33s at ~7 tok/s on TRUE CPU (`num_gpu=0`).
- M017's §9 laptop verdict ("meets targets") is retracted for no-GPU
  hardware. True-CPU verdict below: no tested model meets the 10s
  clarification target with usable quality.
- Relative M017 findings still hold (think-off effect, context-cap
  effect, blind vision, budget scales).
- All M018 challenge timings are GPU-flavored unless labeled CPU.
  The bench now records `processor` per run so this cannot recur.

## 1. Challenge design

20 scenarios (§2 list, see `scenarios.py`), each a remote-or-local
technician case with scripted answers, scripted test outcomes, honest
don't-know/can't-do fallbacks, and hidden behavioral checks. The
simulator drives REAL app interfaces (intake + turns via TestClient),
one POST per turn, max 6 turns (5 for the Spark subset). Models receive
only the opening + answers — never checks or reference outcomes.

Contamination discipline: scenarios/rubric written before full runs;
generic neutral beats (version/reboot) registered in the rubric before
full runs; post-run changes were app-architecture or documented
check-design fixes, each followed by re-runs (record runs below all
use identical prompts).

## 2. Results

### Automated checks + engagement (record runs, identical prompts)

| model | checks | turns | questions | unusable tasks | model calls | wall |
|---|---|---|---|---|---|---|
| gemma4:e4b | 135/142 | 117 | 137 | 12 | 274 | 1528s |
| qwen3:4b (r3) | 132/142 | 97 | 103 | 3 | 234 | 744s |
| qwen3:4b (r2, old prompts) | 133/142 | 112 | 140 | n/a | 264 | 761s |
| llama3.2:3b | 132/142 | 82 | 83 | 14 | 204 | 656s |
| llama3.2:1b | 130/142 | 50 | 46 | 34 | 140 | 337s |
| muse-spark-1.3 (6-scn subset) | 41/45* | 30 | 51 | 0 | 44 | 649s |

\*41/45 after the documented `interpret_error_code` check fix (6/6
scenarios ran; outlook re-run 7/7).

Automated checks barely separate the models (130-135) — engagement
does. The 1B's 130/142 is vacuous-pass inflation: short stalled runs
pass structural checks (no tools, valid citations, question caps) by
doing nothing. Human grades carry the real verdict.

### Human quality grades (developer transcript reads, 1-5)

| model | mean | best | worst pattern |
|---|---|---|---|
| muse-spark-1.3 | 3.83 | immediate two-axis scoping, adapts to answers | repeats when starved; verbose compounds |
| gemma4:e4b | 3.45 | precise scoping, real revision, cites evidence | slow (~2x wall); make/model filler late |
| qwen3:4b r2 | 2.6 | genuine revision; good screenshot handling | 22% vacuous "specific details" questions |
| llama3.2:3b | 2.5 | decent openers; good restraint case | Event-Viewer fixation; repeats verbatim |
| qwen3:4b r3 | 2.1 | DNS pivot after contradiction (best qwen run) | error-message monoculture; earlier stalls |
| llama3.2:1b | 1.1 | — | echoes, fabrications, unsafe advice (below) |

Blind calibration: 10 transcripts (2 scenarios x 5 models) re-scored
blind: 7/10 exact match, 3/10 within ±1 (both directions), rank order
preserved. Per-scenario grades + notes: `grades-*.json` beside each run.

### Stable failures (all local models, both qwen runs)

Never-scoped scenarios: teams-doc-access, app-freeze, dock-monitors
(decisive branches unpursued); windows-update-stuck (never disk space);
slow-device (never onset); impossible-test (never proposed the blocked
test, so adaptation untested); wrong-code (code verification rare —
only gemma did it fully). Unresolvable restraint failed twice (7-9
questions vs cap 6).

### Per-model verdicts

- **gemma4:e4b — best local investigator.** Only model to verify AND
  use a corrected error code, textbook local-vs-SharePoint scoping,
  immediate pivot after disproof, reads evidence (cited ev-1 boot
  time). Costs: ~2x wall time, 9.6GB disk (3.2GB resident), vision
  blind 3/3 (M017) — text role only.
- **qwen3:4b — fast default, shallow judgment.** Revises hypotheses
  for real, handles screenshots honestly, near-zero unusable output
  (3/234). But rarely scopes, fixates, repeats; prompt steering
  removed vacuity (22%→0%) yet narrowed it into an error-message
  monoculture with earlier stalls — prompt tweaks don't fix judgment.
- **llama3.2:3b — viable Meta alternative, not better.** Matches qwen
  structurally (132/142) with fewer questions; genuine Meta
  open-weight run (downloaded 2026-10-28, Community License). Leans on
  generic Event Viewer questions, repeats verbatim, failed the disk
  disproof behaviorally (fragmentation x6 after 200GB-free).
- **llama3.2:1b — not usable.** Quality 1.1: echoes problems as
  questions, invents readings ("heartbeat consistently below 100ms",
  phantom event-log warnings), 34/140 calls unusable, and one
  safety-relevant failure: advised CREATING AN ADMIN ACCOUNT to bypass
  the no-admin constraint. Fast on CPU (~8s triage) but disqualified
  on quality/safety. Profiled as do-not-select.
- **muse-spark-1.3 — a class above in reasoning.** 44 live calls
  (37 subset + 7 verification re-run; authorized). Scopes on turn 0,
  tracks known-vs-unknown explicitly, rules hypotheses OUT. Same
  repetition disease when starved, and verbose (9-12 questions where
  6-8 fit). Value-add over local: first-round judgment and answer
  adaptation, not safety (no local model violated measurement
  boundaries either).

## 3. True-CPU numbers + the 8GB verdict (M018 §6)

`--num-gpu 0`, verified 100% CPU via `ollama ps`:

| model | triage (cold/warm) | plan (warm) | tok/s | resident |
|---|---|---|---|---|
| qwen3:4b | 33s / 25s | 33-34s | ~7 | 3.3GB |
| llama3.2:3b | 32s / 16s | 10s* | ~9 | 2.7GB |
| llama3.2:1b | 16s / 8s | 9s | ~17 | 1.6GB |

\*3B plan rep-1 needed a repair retry (68s); rep-2 10.4s.

A full CPU-only scenario (qwen3:4b, teams): 2 turns in 129s, same 6/7
checks — works, ~7x slower than GPU. Per-turn CPU cost ≈ 60s makes a
6-turn investigation a 6+ minute wait, on a fast desktop i7; a laptop
U-series would be worse.

**8GB-laptop verdict: FAIL for interactive use.** No tested model meets
the 10s clarification target on CPU with usable quality (1B meets it
at 8s but is disqualified). Memory fits (1.6-3.3GB + ~0.4GB backend +
Windows), speed does not. Honest paths forward: any GPU (even modest)
restores interactivity; or cut per-turn calls (triage XOR plan);
streaming UX to shorten perceived waits; cloud escalation with
consent. No lower-spec hardware was available; all results Fury-labeled.

Idle behavior: ~15 min after load, Ollama holds ~84MB (server+tray);
models unload via keep-alive. Cold load ≈ first-call latency above.

## 4. Screenshot investigation (M018 §7)

qwen3-vl:8b on a NEW dialog (win_error.png, Windows Update 0x80070005):
pixel-exact extraction twice (app/title/text/code), 73-84s on GPU.
Text-only fallback (technician transcription) works: every model run
passed the screenshot scenario's asked-content and no-prior-claim checks
(qwen 8/8, gemma 8/8, 3B 8/8; 1B passed structurally with poor follow-up). No model claimed to see an image it
couldn't (withheld warnings verified).

Architecture note: the app runs ONE local model per investigation, so
there is no VL-reads-then-qwen-reasons pipeline in product; VL-as-model
does both, weakly on text (M017: 2/13). Practical alternative on
ordinary hardware: text model + technician transcription (measured
working), VL reserved for GPU workstations. No screenshots went to any
cloud in M018.

## 5. Safety findings

- No model ran host measurements for a remote target (all runs).
  Spark's single remote tool call was `interpret_error_code` (static
  decode) — correct behavior; rubric clarified after mis-flagging it.
- No model proposed or executed an intervention (local path cannot;
  Spark didn't on these scenarios). No invented citations in any run.
- Quality-adjacent hazards (all 1B, plus qwen chkdsk): 1B advised
  creating an admin account and invented readings (disqualified);
  qwen3:4b suggested `chkdsk /f` casually, once for a NETWORK share
  (wrong tool for the fault domain), and invented a `get_system_load`
  tool name. gemma/3B/Spark: no safety flags.
- 1B's 130/142 automated score is the cautionary tale: structural
  checks pass vacuous runs; engagement + human grades are mandatory.

## 6. Fixes from findings (all architectural + re-tested)

1. Local path collected ZERO host evidence on local targets → now
   runs the bounded symptom-triaged sweep before tasks
   (`_run_tool_plan` shared with simulated; +2 regression tests).
2. Reassess never saw asked questions → now receives the last 6
   (repeat context); triage bans "more details" questions.
   Before/after: vacuous questions 22% → 0% (but error-message
   monoculture + earlier stalls — documented above).
3. Internal fallback notes leaked as technician questions AND
   hypothesis titles ("triage did not answer") → technician-meaningful
   fallbacks + regression test. (One qwen run troubleshot ITSELF after
   reading the leak — the fix was load-bearing.)
4. Rubric/check fixes (documented, re-run): `interpret_error_code`
   exempt from target checks; no-admin check contradicted its premise
   (opening already states no admin) → acknowledgment check.
5. Bench: `--num-gpu`, per-run `processor` from /api/ps, GPU in host
   info, `--vision-image` override; challenge: `--num-gpu`,
   `--max-turns`, `--live` guard, engagement metrics in transcripts.

## 7. Human-in-the-loop demo (M018 §9)

Unseen synthetic issue (not in the 20): "Bluetooth headphones pair but
produce no sound", gemma4:e4b local, remote target, OFFLINE stack.
Technician (developer) answered 3 genuine turns:

1. Model: check Device Manager audio profile (HFP/Stereo?) — exactly
   right. Tech: present in Bluetooth, absent from Sound output.
2. Model: reassessed (initialization failure) → re-enable the profile
   in Sound settings — correct next step. Outcome: useful guidance,
   correctly unresolved (nothing remotely verifiable).

Assets: `docs/assets/fieldrook-m018-tour.webm` (37s real local round)
+ 4 screenshots. Shortcomings shown honestly: stale fallback questions
linger unanswered; no verification possible remotely.

## 8. Hackathon evidence (M018 §10)

- Muse Spark: primary reasoning via Model API; 44 measured live calls
  in M018 (authorized, synthetic fixtures only); value-add quantified
  above (3.83 vs 3.45 best local on the subset).
- Meta open-weight: Llama 3.2 1B+3B downloaded with authorization and
  run through the identical 20-scenario challenge (132/142 + 2.5/5 for
  3B; 1B disqualified with documented reasons). Real local-only use.
- Agentic tools, human-in-the-loop, local-first, evidence verification:
  exercised by every scenario run (264+204+140+274 local calls).
- Rules review (web, 2026-10-28): scoring is impact 30%, creative
  Meta-tool use 25%, demo+video 25%, technical depth 20%. NO
  prize-category or open-weight eligibility is claimed — usage is
  documented, eligibility is for the organizers.
- Differentiator vs chatbot: bounded tools, target isolation, cited
  evidence, measured verification, and now measured model comparison.

## 9. Definition-of-done answers

- Best local model: gemma4:e4b on quality (3.45), qwen3:4b on
  speed/reliability; llama3.2:3b a viable Meta alternative; 1B out.
- Unfamiliar incidents: yes with caveats — scoping is the weak spot
  for every local model; Spark scopes immediately.
- Wrong first hypothesis: yes — every model revised at least once
  (verified in transcripts); 3B/1B weakest behaviorally.
- Reported vs measured: enforced structurally (source labels);
  screenshot-withheld path verified; no violations observed.
- Other computers: yes — remote targets collect zero host
  measurements across 100+ scenario runs.
- Fast enough locally: on GPU yes; on CPU no (25-65s/turn).
- Ordinary laptop: interactive use FAILS the 10s target on CPU with
  usable quality; memory fits, speed doesn't.
- Spark value-add: first-round judgment + adaptation (3.83 vs 3.45);
  same repetition disease; 44 calls for 6 scenarios.
- Unsolved: scoping instinct, pivot-on-starvation, CPU interactivity,
  VL text reliability, gemma vision blindness.
- Ship priorities (M019): per-turn call reduction, streaming UX,
  repetition guardrails, laptop-GPU/NPU evaluation, Spark verbosity
  caps.

## 10. Invocation accounting (M018 §11)

Local: qwen r1 248 + r2 264 + r3 234 + CPU-scn 6, 3B 204, 1B 130+140,
gemma 274, VL vision 2, CPU bench 12, mem probe ~1 ≈ 1,515 loopback
calls, zero cloud. Live: 44 Muse Spark calls (authorized subset +
verification). Results dirs list every per-scenario count.
