# M041 — Local Cold-Start Reliability & Bounded Triage Recovery

**Date:** 2026-11-25 (Europe/Stockholm)
**Branch:** `m041/local-cold-start-recovery`, based on `m040/real-incident-evidence` (`0bc2088`)
**Release:** published `v0.6.0-rc.4` unchanged; no new installer has been built.

## Observed problem

In the retrospective Fury Bridge incident replay (2026-11-24), Qwen3 4B's first local model triage took **145.1 s** and its triage returned a ReadTimeout, after which FieldRook used deterministic fallback. Later calls on the same model were quick. This is a **single run** and should not be assumed to be representative.

Prior to M041, `LocalEndpointProvider.run_task` used `TASK_LIMITS[task]["timeout"]` for each local HTTP request, but HTTPX's per-operation timeout did not enforce a single task-level wall-clock deadline. A second JSON-repair request could also run a new full timeout. Actual elapsed time could exceed the intended per-task budget.

## Changes implemented

### Shared wall-clock budget for local tasks

`backend/app/analysis/provider.py` now uses one monotonic deadline for **all local task work**, including the API style probe, the primary model request, optional timeout retry and optional JSON repair.

- Uses `asyncio.wait_for` around each request and JSON repair, with only the remaining task budget.
- Cancels the await on deadline expiration; this limits the FieldRook wait, but a model server may still finish a previously started generation in its own process.
- All existing task limits remain the same. This does not change model temperature, prompt content, token cap, tool permissions or provider configuration.

### Exactly one timeout-only retry for triage

Only **initial triage task calls** reserve up to 25 seconds (25% of budget if smaller) for one retry. If the first attempt times out or reports a transient HTTP timeout, FieldRook may try again **once**, without extending the original deadline. This is useful if a local model had an intermittent loading delay; it is **not guaranteed** to recover every cold load or to improve performance on every machine.

- HTTP 4xx, model-not-found, malformed JSON and other permanent errors are **not** silently retried.
- Reassess, plan and other tasks do **not** replay inference because retrying those tasks would duplicate work or increase latency.
- Existing cancellation remains authoritative: a technician-requested cancellation propagates and does not turn into fallback.
- If both attempts fail or a deadline expires, the result is explicitly recorded as **no model reasoning**, and deterministic fallback can continue the case instead of pretending a live model analyzed it.

### Observable task provenance

Local task statistics include `task`, `status` (started/model/failed), `attempts`, `retry_used`, `task_wall_s` and controlled failure category. The activity log displays the **whole task elapsed time**, distinguishing this from Ollama's own generation time. Recovered retries and fallbacks are recorded in warnings, not passed off as ordinary inference.

Prior successful inference statistics are cleared at the start of each task to prevent stale model-speed numbers appearing after a failed request.

## Automated verification

New regression file: `backend/tests/test_m041_cold_start.py`.

Cases include:
1. The first attempt times out and a single retry produces a usable model JSON answer inside one deadline.
2. Both attempts time out and return labeled fallback under the same deadline.
3. An HTTP 400/model configuration error is **not** retried.
4. Wrapped `httpx.ReadTimeout` is retryable once.
5. Follow-up reassessments do not duplicate slow inference.
6. JSON repair consumes the **remaining** budget, never a fresh timeout.
7. A successful JSON repair is distinct from a timeout retry.
8. Explicit technician cancellation propagates, not fallback.
9. Old model inference statistics are not reused after a failed task.

Targeted regression run (M041 + local tasks + assist + information gain + M040 + evidence integrity): **204 passed, 1 pre-existing deprecation warning**. Full-suite outcome documented below after isolated verification.

## Real local-model test (NOT a mock)

An independent replay of the same historical Fury Bridge case was conducted using the real FastAPI investigation endpoints, local **Ollama Qwen3:4B**, no fixtures and a fresh isolated SQLite file. Before the run, Ollama's loaded-model endpoint reported **no loaded models**.

- `backend/eval/results/m041-cold-replay-20261125/run_real_bridge.py`
- `backend/eval/results/m041-cold-replay-20261125/qwen3-4b/progress.json`
- `backend/eval/results/m041-cold-replay-20261125/qwen3-4b/turn-0-snapshot.json`
- `backend/eval/results/m041-cold-replay-20261125/qwen3-4b/final-case.json`

**Observed on this machine only:**

- First **API intake** round: **13.1 s** total.
- Local model triage task: **10.98 s** total (190 generated tokens in 2.3 s, first token 8.62 s).
- The first triage returned a real **live local model** result with **no warnings, no timeout, and no fallback**.
- The remaining four rounds: **2.5, 2.5, 2.7, 2.3 s**.
- All five steps completed with `analysis_mode=live`, `uses_fixtures=false`, `tool_calls_used=0`, remote diagnostic target and zero corrective host actions.

**Interpretation:** This verifies that M041 retains usable real cold-start inference on Fury. It does **not** prove the old 145.1 s transient issue is eliminated; warm-cache state, GPU scheduling, run-to-run randomness and Ollama load may differ. A real cold load **that actually times out** was not reproduced in this live test; timeout recovery was verified deterministically through mocked-delay regression tests.

## Remaining issues

- Qwen3 4B sometimes produced weak or contradictory initial permission hypotheses despite the launcher being reported as still running. This belongs in diagnostic reasoning quality follow-up, not the timeout/retry fix.
- A local model might continue working after FieldRook stops waiting; bounded retry must not be confused with a guaranteed server-side cancellation.
- No fresh GUI installer, AV/SmartScreen qualification, external tester results or statistical latency benchmarks were included.
- Keep remote-target diagnostic isolation and technician approval rules unchanged.

## Next action

After code review and a clean broad regression run, push this as its own development branch. Do **not** change the public rc.4 download. Plan an rc.5 candidate only after a clean-machine installation check and an explicit technician pilot.

## Full suite

First broad run overlapped the live Ollama replay and a demo-worker heartbeat test hit its 20s startup deadline (no assertion about local AI). The same isolated worker test later **passed** in 14.22 s. On a separate **full-suite rerun without concurrent Ollama generation**, all **925 tests passed**, **4 skipped**, **2 warnings**, in **211.37 s**, exit code 0. This is the verified final M041 backend result.
