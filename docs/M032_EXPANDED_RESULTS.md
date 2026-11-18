# M032 — Expanded Gauntlet & Repeated Teams Runs

**2026-11-18 · Evaluation branch `m032/diagnostic-gauntlet` · Baseline production behavior unchanged**

These are actual local-model calls to Fury's Ollama, using isolated
temporary investigation databases. They are **not** hosted model
results, formal blinded human scores, or clinically/statistically
significant model rankings.

## A. Additional cases (same registered M032 suite, max 3 turns)

| Case | Model | Structural checks | Wall clock | Model calls | Real observed failure |
| --- | --- | ---: | ---: | ---: | --- |
| Outlook 0x80070005 | qwen3:4b | 6/7 | 13.1s | 3 | Failed `distinguished`: did not pursue safe-mode, recent-change or failure-point branch |
| Outlook 0x80070005 | qwen3:8b | 6/7 | 17.7s | 3 | Same failure |
| Intermittent VPN | qwen3:4b | 7/7 | 5.2s | 2 | No structural check failed; 1 turn |
| Intermittent VPN | qwen3:8b | 7/7 | 10.5s | 4 | No structural check failed; 3 turns |

These scenario checks do not certify ideal investigation quality.
Especially in the Outlook case, both models chose broad scope/registry
questions instead of more discriminating safe-mode / onset checks.

## B. Teams/Excel repetition — fixed V2 suite, 2 additional runs each

| Model | V2 original | Repeat 1 | Repeat 2 | Full 11/11 |
| --- | --- | --- | --- | --- |
| qwen3:4b | 11/11 (16.3s) | 10/11 (14.8s) | 11/11 (8.4s) | **2/3** |
| qwen3:8b | 11/11 (18.5s) | 11/11 (16.9s) | 11/11 (9.3s) | **3/3** |
| qwen3-coder:30b | 11/11 (64.1s) | not repeated | not repeated | 1/1; insufficient reliability data |

4B's Repeat 1 failed the *immediate same-file corruption* rule: after
another user opened the same file, it left `Corrupted Excel files in
Teams sync` **active** until a later unrelated `I don't have that
information` response.

**Both 4B and 8B** repeatedly weakened additional hypotheses on the
`I don't have that information` turn even though no additional
diagnostic data was supplied. This is an independent **semantic
integrity problem not covered by 11/11 structural scores**.

The runs also have warm/cold-load variance. Wall times observed here
do not isolate inference tokens per second or GPU residency. Do not
claim 8B is statistically better based on only three repeats.

## C. Frozen baseline files (intentionally Git-ignored)

- `backend/eval/results/m032-pilot-v2/`
- `backend/eval/results/m032-expanded/`
- `backend/eval/results/m032-repeats/`

Each directory contains JSON summaries and human-readable transcripts;
their scenario/check data are never given to the model as instructions.

## D. Engineering decision

**M033-B target: distinguish *no new information* from evidence that
contradicts a hypothesis.** On a thin technician answer such as
`I don't have that information`, the system must preserve earlier
hypothesis statuses if there is no newly collected measurement or
authorized image evidence. It may still ask a different safe question
or recommend a check. The action must be visible in provenance logs.

This needs both a deterministic acceptance-test guard and a prompt
instruction; only editing the prompt is too weak. Keep the original
M032 baselines for pre/post comparison. Do not add case-specific
"Teams" shortcuts to production code.

A second improvement candidate is better *information gain* in the
first question for Outlook, Teams and VPN. Measure separately rather
than slipping it into the same patch.
