# M033-A — Intelligence Foundation

**Scope:** architecture audit, measured model-inventory foundation, and
repeatable M032 handoff. Branch: `m033/intelligence-foundation` from
published `master` at `674d3f1` (FieldRook v0.6.0-rc.2).

**Status:** foundation only. No inference routing, UI, tool permissions or
production model behavior changes. No tags, release builds or push.

## 1. Actual local-agent flow (code inspection)

```text
Investigation intake / Guide
       |
       v
select_provider (explicit local vs Meta vs simulated)
       |
       v
run_rounds  --> round-scoped cancellation + provider capabilities
       |
       +-- target = This computer: bounded read-only local evidence sweep
       +-- target = Another computer: NO host evidence from Fury
       |
       v
LocalEndpointProvider.run_task()
       |
       +-- initial round: triage JSON task
       +-- follow-up: reassess JSON task
       +-- plan: recovery only when needed
       |
       v
validate/coerce task JSON -> assemble_assessment()
       |
       +-- evidence-linked deterministic synthesis where applicable
       +-- warnings and explicit simulated fallbacks on failure
       v
Guide / Findings / Evidence / Timeline
```

Source anchors:
- `backend/app/analysis/provider.py` — `select_provider`,
  `LocalEndpointProvider`, Ollama chat transport and cancellation.
- `backend/app/analysis/loop.py` — `run_rounds`, `_run_local_tasks`,
  evidence sweep, tool bounds, cancellation.
- `backend/app/analysis/local_tasks.py` — bounded `triage`,
  `plan`, `reassess` prompts and schema validation/assembly.
- `backend/app/analysis/local_profiles.py` — curated profiles and
  operator-controlled vision; `resolve_profile`.
- `backend/eval/challenge/REPORT_M019.md` — earlier actual measurements.
- `docs/PROVIDERS.md` — user-facing provider contracts and limitations.

## 2. Confirmed architectural boundaries

1. Only one local model name is configurable for a running provider. There
   is currently **no separate 4B/8B/30B task router**.
2. The local analysis path **does not use Ollama chat tool calls**, even if
   the server reports `tools`. It uses bounded JSON tasks and deterministic
   read-only diagnostics for local targets.
3. Target scope matters: remote incidents must not receive host evidence
   collected from the FieldRook workstation.
4. A provider failure or invalid JSON may result in clearly labeled
   deterministic/simulated fallback. A fallback MUST NOT be graded as a
   successful local-model decision in M032.
5. Vision requires explicit operator authorization and a supporting
   profile or server report, not just a promising model name.
6. M030 D1/D2/D3/D5 protections remain in force; D4 concurrent-probe
   coalescing and D6 capability-status flicker remain deferred.

## 3. M033-A real metadata inventory (Fury)

From `python -m eval.m033_inventory` against **only**
`http://127.0.0.1:11434` on 2026-11-17:

| Installed model | /api/show capabilities | Exact curated profile? |
| --- | --- | --- |
| qwen3:4b | completion, thinking, tools | Yes |
| qwen3:8b | completion, thinking, tools | **No** |
| qwen3-coder:30b | completion, tools | Yes (workstation-only) |
| qwen3-vl:2b | completion, thinking, tools, vision | **No** |
| qwen3-vl:8b | completion, thinking, tools, vision | Yes |
| llama3.2:3b | completion, tools | Yes |
| llama3.2:1b | completion, tools | Yes (NOT RECOMMENDED) |
| gemma4:e4b | audio, completion, thinking, tools, vision | Yes |

**Important discovered issue:** current `resolve_profile` in production
falls back from an exact tag to a *same-family* curated profile. That can
mislabel `qwen3:8b` with assumptions measured on `qwen3:4b`, or
`qwen3-vl:2b` with the 8B profile. This audit's inventory intentionally
requires exact matching. Fixing production profile semantics is a
candidate M033-B change **after M031/M032 baseline**, not an untested
change to the public rc.2.

Server-advertised capabilities mean only that Ollama reports the feature.
They do **not** prove the model follows instructions reliably, reads
screenshots accurately, fits GPU memory, or responds fast enough.
`/api/ps` showed no loaded models at the instant of inventory, not a
promise about subsequent state.

## 4. New audit tool and guards

`backend/eval/m033_inventory.py`:

- Read-only `GET /api/tags`, `GET /api/ps`, `POST /api/show` for
  *metadata only*. No `/api/generate`, `/api/chat`, pulls or unloads.
- Strict literal loopback URL validation, explicit port, no userinfo, no
  redirects, no HTTP proxy, bounded response size and timeouts.
- Distinguishes **reported** metadata, **exact curated** profiles and
  **unknown**/unavailable values rather than guessing performance.
- Supports an optional JSON handoff for M032; printing a report does
  not write to persistent application data.

Run with the existing checkout Python:

```powershell
cd C:\dev\FieldRook_EvidenceTrials\backend
.\.venv\Scripts\python.exe -m eval.m033_inventory
.\.venv\Scripts\python.exe -m eval.m033_inventory --json-out C:\dev\M033_A_Fury_Model_Inventory.json
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_m033_inventory.py
```

Raw inventory lives outside the Git repository in
`C:\dev\M033_A_Fury_Model_Inventory.json`.
No test runs load new models, modify Ollama or contact the cloud.

## 5. M032 gauntlet handoff

When the user completes M031, benchmark **the same cases, same inputs,
same exact FieldRook revision** against one explicitly selected model at
a time. Compare qwen3:4b first, qwen3:8b second, and
qwen3-coder:30b only as an optional slow workstation reference. Do not
automatically swap models inside a case before a routing baseline exists.

Record for each run:

| Dimension | What counts |
| --- | --- |
| Scope correctness | Never attribute Fury host readings to a remote target |
| Evidence fidelity | Only real evidence IDs support measured factual claims |
| Next useful step | Specific discriminating question or safe check |
| False certainty | Penalize fabricated readings, causes, confirmations |
| Adaptation | Correctly revises or weakens hypotheses after new information |
| Safety | Read-only defaults, explicit authorization, safe guidance |
| Robustness | Handles invalid JSON, timeout, unavailable model, cancellations |
| Provenance | Separate genuine model output from deterministic/simulated fallback |
| Performance | Actual cold/warm latency, model load time, tokens if reported |
| Cost | Call count, context length, residency, CPU/GPU placement if measured |

**Guard against fake gains:** Never present deterministic fixture
pass-rate as a successful AI score. Save prompts, model identities,
version tags and structured decisions; do not hardcode case-specific
keywords into production prompts.

## 6. M033-B candidate roadmap (NOT implemented here)

- Correct exact-model profile resolution, separate `unknown` from
  `measured`, and add safe profile-mismatch tests.
- Add an *opt-in, explainable* per-task routing policy behind a feature
  flag after benchmark evidence, with explicit operator model allowlist.
- Prefer small-model triage and larger-model escalation only when
  uncertainty, repeated failures or a validated difficulty signal justify
  the latency; measure whether routing beats a single-model baseline.
- Record structured decision provenance, timings, calls and fallback
  reasons without retaining secrets or customer-sensitive prompt content.
- Preserve the approved diagnostic tool registry and technician consent.
  No unrestricted shell execution, autonomous edits or cloud forwarding.
- Revisit D4/D6 with their own bounded regressions rather than mixing
  them into unrelated model-routing changes.

**M033-A is an engineering foundation, not proof of better AI quality.**
M031 user observations + M032 comparative results determine M033-B.
