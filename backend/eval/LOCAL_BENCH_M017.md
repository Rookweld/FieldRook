# M017 local-inference benchmark report

Date: 2026-10-28. Host: Fury workstation (i7-13850HX, 68.4GB RAM,
28 logical CPUs, CPU-only Ollama). All inference went to loopback
Ollama; zero cloud calls. 35 local-model requests across 9 bench runs.

Harness: `backend/eval/local_bench.py`. Tasks use the production
prompts and budgets from `app/analysis/local_tasks.py`:

- triage (220 tokens / 120s), plan (380 / 180s), reassess (220 / 120s),
  synthesize (bench-only), vision (dialog fixture `m17dialog.png`, 240s).
- Provider path: Ollama native API, `think=false`, `num_ctx=8192`.
  qwen3-vl:8b gets `task_budget_scale=8.0` (it always thinks).
- Memory = resident Ollama model allocation during the task
  (`loaded_model_size`); tok/s = Ollama `eval_count/eval_duration`.

Raw JSON transcripts stay in the git-ignored `results/local-bench/`
directory; this file is the committed record.

## Context cap: the single biggest win

qwen3:4b with uncapped context vs `num_ctx=8192` (same prompts):

| run   | triage | tok/s | resident |
|-------|--------|-------|----------|
| uncapped (0529) | 15.1s cold | ~27 | 14.4GB |
| capped (0530)   | 6.5s cold  | ~92 | 3.3GB  |

Uncapped KV cache ballooned a 2.5GB model to 14.4GB. The 8192 cap
is now the production default for local task calls.

## Per-model results (final configuration)

### qwen3:4b — recommended default for local text

| task  | cold | warm (3 reps) | tok/s | mem | valid |
|-------|------|---------------|-------|-----|-------|
| triage | 6.5s | 11.1 / 2.3 / 2.7s | ~90 | 3.3GB | 5/5 |
| plan   | 3.5s | 3.7 / 3.3 / 3.7s  | ~95 | 3.3GB | 5/5 |
| reassess | — | 3.1s | 27* | 3.3GB | 1/1 |
| synthesize | — | 9.3s | 31* | 3.3GB | 1/1 |

\*(reassess/synthesize measured pre-cap; warm capped runs are faster.)

Warm triage lands in ~2.5s, plan in ~3.5s. First rep after a model
switch (11.1s) pays the load cost. Quality: valid JSON every run,
safe technician-scope steps, sensible hypotheses. Triage questions
are relevant but narrower than gemma's (asks about Teams version
rather than scoping Excel-vs-all-files). One run emitted a
`TECH:CHECK` step kind; the normalizer coerced it to
TECHNICIAN_CHECK and now records a warning. Meets the M017 §9
targets (clarification <10s, plan <30s).

### qwen3-vl:8b — vision role only

| task | wall | valid | note |
|------|------|-------|------|
| triage | 13–69s | 0/4 | thinking exhausts even the 8x budget |
| plan | 13–112s | 0/3 | same; high variance run to run |
| reassess | 8–26s | 1/3 | 15.6s valid run was good |
| synthesize | 31–96s | 1/3 | valid run overclaims likelihood ("high") |
| vision | 10.2s | 1/1 | exact app/title/code/error text |

The VL model ignores the think-off switch (~1500 thinking tokens,
~6500 chars before answering). Text tasks are too slow and too
flaky for the default path despite 8x budgets. But vision is
excellent: it read the synthetic dialog exactly (ContosoApp,
0x80070005, full error text) in 10.2s. Profiled as the
screenshot-case model, never the default.

### gemma4:e4b — sharp text, blind vision

| task | wall | valid | note |
|------|------|-------|------|
| triage (cold) | 17.1s | yes | best triage question of any model |
| plan | 12.3s | yes | valid after one JSON repair retry |
| vision x3 | 1.4 / 17.3 / 1.2s | 0/3 | all-null on a known-readable dialog |

MoE behavior confirmed: 9.6GB on disk, only ~3.2GB resident,
~70 tok/s on CPU. Its triage question ("can the user open ANY file
type from Teams, or only Excel?") correctly scopes application vs
integration layer — the best diagnostic question measured. But
vision returned null for every field 3/3 despite the server
advertising vision and accepting the image (recorded as
`blind_vision`). Text alternative to qwen3:4b; do not trust it
with screenshots until re-verified.

### qwen3-coder:30b — workstation reference, excluded from laptop role

| task | wall | valid | note |
|------|------|-------|------|
| triage (cold) | 46.1s | yes | good question, ~26 tok/s |
| plan | 29.1s | yes | valid after one repair retry |
| vision | 3.0s | no | HTTP 400, multimodal rejected |

19.2GB resident, ~26 tok/s. Valid structured text but far outside
laptop budgets and 10x slower than qwen3:4b warm. Profiled as
workstation-only; text-only (server rejects images).

## Not measured

Meta Llama 3.2 1B/3B Instruct are not installed on this machine and
were not downloaded (no authorization for model downloads).
Profiles carry install hints (`ollama pull llama3.2:1b`, ~1.3GB;
`ollama pull llama3.2:3b`, ~2.0GB) and stay unrecommended until
measured. No Meta open-weight eligibility is claimed in M017.

No lower-spec laptop was available; all numbers are Fury CPU-only.
Laptop-class verification remains future work.

## Acceptance verdict (M017 §9)

- First useful clarification <10s: PASS for qwen3:4b warm (2–3s),
  cold (6.5s), gemma4 cold (17.1s MARGINAL), VL/30b FAIL.
- Short plan <30s: PASS for qwen3:4b (3.5s) and gemma4 (12.3s);
  30b borderline (29.1s); VL FAIL.
- No multi-minute blocking without feedback: PASS — Guide shows
  elapsed time plus cancel; backend honors cancel between calls.
- Memory stays laptop-safe: PASS for qwen3:4b (3.3GB) and gemma4
  (3.2GB); VL 6.0GB marginal for 8GB machines; 30b excluded.

## Quality grades (transcript review, 8 M017 §10 axes)

| axis | qwen3:4b | qwen3-vl:8b | gemma4:e4b | coder:30b |
|------|----------|-------------|------------|-----------|
| relevant questions | good | unmeasured* | best | good |
| practical checks | good | unmeasured* | good | good |
| evidence handling | valid JSON 12/12 | flaky | valid +1 repair | valid +1 repair |
| target respect | remote-scope kinds only | n/a | remote-scope kinds only | remote-scope kinds only |
| safety | no escapes observed | no escapes observed | no escapes observed | no escapes observed |
| uncertainty | unknowns listed | overconfident synth | unknowns listed | adequate |
| structured reliability | 12/12 first-try | 2/13 text, vision 1/1 | 2/3 (+1 repair) | 2/2 (+1 repair) |
| latency | best | worst | middle | slow |

\*VL text tasks rarely produced gradable output; its grade is
vision-only (exact dialog read, 10.2s).

Failure examples are part of the record: VL thinking exhaustion
(raw 6469-char thinking prefix captured), gemma 3/3 blind vision,
coder HTTP 400 on images, qwen3:4b `TECH:CHECK` kind typo
(coerced + warned). No axis was benchmarked on happy paths alone.
