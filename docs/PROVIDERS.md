# FieldRook inference providers (M016-M017)

FieldRook separates **inference provider** (where intelligence runs) from
**diagnostic target** (which computer the evidence describes). The two are
never conflated: a local model can guide a remote-computer investigation,
and the Meta cloud model never receives host measurements for a machine it
cannot see.

## The three providers

| Provider | Selection | Processing | Vision | Tool calling | Notes |
| -------- | --------- | ---------- | ------ | ------------ | ----- |
| `meta` | `MODEL_API_KEY` set (auto) or explicit | Meta cloud | yes | yes | Primary live reasoning; screenshots need consent |
| `simulated` | no key, `FIELDROOK_OFFLINE=1`, or explicit | none | no | no | Deterministic fixtures; never claims model reasoning |
| `local` | explicit only | this computer | configurable | configurable | OpenAI-compatible loopback endpoint (Ollama, llama.cpp) |

Capabilities are declared by each provider and **enforced by the loop**:

- A provider without vision never receives image bytes (screenshots are
  withheld with a warning, not silently dropped).
- A provider without tool calling gets a plan-only path: it reasons over
  reported observations and returns the assessment JSON, and is never shown
  tool definitions it cannot use.
- A provider that fails (timeout, bad output, unreachable endpoint) falls
  back to simulated analysis with an explicit warning. The round never
  hangs and never fabricates a result.

List providers and their live availability at `GET /api/providers` (static
configuration only; the endpoint never probes the network).

## Selecting a provider

- Server default: `FIELDROOK_MODEL_PROVIDER=auto|meta|simulated|local`
  (`auto` keeps the legacy key-or-simulated behavior).
- Per investigation: the intake `provider` field or the Guide's provider
  switcher. The choice is stored on the investigation and applies to the
  next round; past assessments keep their original labels.

## Switching privacy

Switching **to** the Meta cloud provider while an investigation holds
screenshots, evidence, or notes requires explicit `confirm_cloud`
authorization, because that content would be transmitted on the next model
round. Switching between simulated and local needs no confirmation.
Downgrading to `auto` clears the override.

## Local endpoint setup

```powershell
$env:FIELDROOK_LOCAL_MODEL_URL = "http://127.0.0.1:11434/v1"
$env:FIELDROOK_LOCAL_MODEL_NAME = "qwen3:4b"
# Only enable what the model actually supports:
$env:FIELDROOK_LOCAL_MODEL_VISION = "0"
$env:FIELDROOK_LOCAL_MODEL_TOOLS = "0"
# Optional API/thinking overrides (defaults are measured-good):
$env:FIELDROOK_LOCAL_API = "auto"     # auto | ollama | openai
$env:FIELDROOK_LOCAL_THINK = "auto"   # auto | on | off
```

Rules:

- The URL must be an `http(s)` **loopback** address (`127.0.0.1`,
  `localhost`, `::1`). Anything else is refused before any request.
- The cloud `MODEL_API_KEY` is never sent to a local endpoint.
- Vision and tool calling default to **off**. Enable a flag only for a
  model known to support it; FieldRook validates behavior (unknown tools
  are downgraded to technician guidance, bad JSON is repaired or replaced
  by simulated analysis).

No local model is required: FieldRook works fully without one, and nothing
is downloaded automatically.

## M017: task-appropriate local reasoning

A small CPU model cannot afford the full-assessment call the cloud path
uses (M016 measured >280s without completing on qwen3:4b). The local
provider therefore runs a bounded task pipeline instead of one giant
request (`app/analysis/local_tasks.py`):

1. **triage** (220 tokens / 120s) — one clarifying question, tentative
   hypotheses, one next check.
2. **plan** (380 / 180s) — structured technician steps.
3. **reassess** (220 / 120s, on new observations) — update hypotheses
   without regenerating the case.

Each task validates its JSON (extract, repair once, coerce unknowns
with warnings) and degrades to the deterministic planner per task —
never presented as model reasoning. M017's "Fury CPU-only" speeds
(triage ~2.5s) were later proven GPU-flavored (M018 erratum in
`backend/eval/LOCAL_BENCH_M017.md`); placement-verified true-CPU
triage is ~25-33s for qwen3:4b. Full numbers and quality grades:
`backend/eval/LOCAL_BENCH_M017.md`, `backend/eval/challenge/REPORT_M019.md`.

Engineering notes from measurement:

- **Ollama native API is preferred** (probed once, then cached):
  `/v1/chat/completions` ignores the think-off switch (103s thinking
  burn vs 11s native on the same prompt). Override with
  `FIELDROOK_LOCAL_API` only if probing misbehaves.
- **Thinking defaults off for task calls** (`FIELDROOK_LOCAL_THINK=auto`).
  Some models ignore the switch (qwen3-vl:8b always thinks); their
  profiles carry a compensating token budget instead. Never assume a
  universal disable flag — this one is Ollama-specific and verified.
- **Context is capped at 8192 tokens** for task calls: uncapped KV
  cache ballooned qwen3:4b to 14.4GB resident; capped it holds 3.3GB.
- The local path never uses chat tool-calling; plans stay in the
  validated technician-step schema (`TECHNICIAN_CHECK`,
  `CLARIFYING_QUESTION`, `EXTERNAL_SYSTEM_CHECK`).

## M017: capability profiles

`GET /api/providers` now includes, for `local`, a `profile` object
from `app/analysis/local_profiles.py` plus the probed `api_style`.
Profiles record measured (not inferred) capabilities: vision,
server tools, context window, performance class, storage, thinking
behavior, install hints, and a notes field with benchmark findings.
Unknown models get a conservative default (text-only, direct answers).

Vision rule, enforced in the loop: screenshots are sent only when
the operator flag is on **and** the profile or server capabilities
support vision. A name alone never implies vision; a flag nothing
supports produces a warning and screenshots stay withheld. Measured
cautionary cases: gemma4:e4b advertises vision but returned null
for a readable dialog 3/3; qwen3-coder:30b rejects images (HTTP 400).

## M017: connection test and cancellation

- `POST /api/providers/local/test` runs one tiny capped completion
  ("Reply with exactly: OK", 30s) and reports reachability, API
  style, latency, profile, server-advertised capabilities, and any
  vision mismatch. It is **user-triggered only** — the Guide never
  polls or preloads models.
- `POST /api/investigations/{id}/cancel` sets a cancel flag
  (persisted `cancel_flags` table). M019 aborts **mid-flight** via
  streaming generation (~0.2s, was ~9s): the in-flight call stops,
  no further calls start, evidence is kept, and the investigation
  stays resumable. The Guide shows live elapsed time and the cancel
  control during a turn, and blocks duplicate submits.

## Deployment direction (ordinary laptops)

Default FieldRook bundles no model and requires none. Measured
verdicts (M018 challenge + M019 placement-verified CPU runs):

- **Default local text model: qwen3:4b** (~2.5GB download, ~3.3GB
  resident, reliable structured output). GPU runs answer in ~2-4s;
  TRUE CPU-only triage is ~25-33s — no 8GB CPU-laptop interactivity
  claim; the in-app profile says so.
- **Screenshot cases: qwen3-vl:8b** (~6GB) as an opt-in second
  model for its exact dialog reads — not as the default.
- **Best local quality: gemma4:e4b** (~9.6GB disk) reasons best but
  needs ~45-73s on true CPU: not interactive there; text use only
  (its vision returned null 3/3 on a readable dialog).
- **Meta open-weight: llama3.2:3b** is usable with repetition and
  fixation caveats (~16-32s true-CPU triage); **llama3.2:1b is not
  a supported reasoning model** (unacceptable M018 quality/safety).
- **Not recommended: qwen3-coder:30b** (19.2GB resident)
  — workstation reference only.

Packaging stays out of M017 scope, but the shape is set: optional
model packs over an existing Ollama install, hardware checks
(memory/storage), and user-controlled install/remove. No silent
downloads, no background model loading.

## Meta open-weight note

M018 measured the genuine lightweight Meta candidates (Llama 3.2
1B/3B Instruct, text-only) on the identical 20-scenario challenge:
3B is a viable alternative (132/142 checks, repetition caveats),
1B is disqualified on quality/safety — see
`backend/eval/challenge/REPORT_M018.md` and the per-model profiles
in `local_profiles.py`. There is no official small Glimmer
checkpoint — Glimmer 30B stays a workstation-class comparison
target, not a laptop requirement.

## M019: single-decision loop

One technician turn now costs one model decision (triage OR
reassess; plan only as recovery): ~4.7x fewer calls than M018 on
the identical challenge with no quality regression (127-131/142
vs 132/142, within run variance; 48/53 on 6 unseen held-out
cases). Questions have a lifecycle (current/answered/superseded/
retired/blocked), manual guidance passes a 6-tier impact filter,
and CPU profiles are placement-verified honest. Details:
`backend/eval/challenge/REPORT_M019.md`.

## M016 smoke test (measured 2026-10-28)

Workstation Ollama (`qwen3:4b`, CPU-only): provider wiring verified
end-to-end — local selection, plan-only path, timeout handling, and honest
simulated fallback with a labeled warning. A full JSON assessment did not
complete within a 280s budget (thinking-model latency on CPU), while a
minimal `/v1/chat/completions` probe answered in 7.2s. Conclusion: the
provider path is compatible; per-model latency/quality benchmarking is
M017 scope. No models were installed, modified, or removed during testing.
