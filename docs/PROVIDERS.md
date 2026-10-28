# FieldRook inference providers (M016)

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

## M016 smoke test (measured 2026-10-28)

Workstation Ollama (`qwen3:4b`, CPU-only): provider wiring verified
end-to-end — local selection, plan-only path, timeout handling, and honest
simulated fallback with a labeled warning. A full JSON assessment did not
complete within a 280s budget (thinking-model latency on CPU), while a
minimal `/v1/chat/completions` probe answered in 7.2s. Conclusion: the
provider path is compatible; per-model latency/quality benchmarking is
M017 scope. No models were installed, modified, or removed during testing.
