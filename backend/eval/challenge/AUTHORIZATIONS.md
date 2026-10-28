# Model-usage authorizations (M018, recorded M019 §0)

M018's report cites 44 live Muse Spark calls and two Ollama model
downloads "as authorized". This file records how that authorization was
obtained, so no future milestone can treat it as standing permission.

## What was authorized, and how

During the M018 session, before any download or cloud call, the agent
asked the operator two explicit structured questions (tool-mediated
choice prompts, each with a do-nothing option):

1. **Llama download** — "May I download Llama 3.2 Instruct models to
   your Ollama (Meta Community License, local use)?" Options: both
   1B+3B / 3B-only / do-not-download.
   Answer: **download both, run the challenge**.
2. **Spark live** — "May I run capped live Muse Spark evaluations
   (uses your API key/credits; exact cost unknown)?" Options: 6-scenario
   subset / full 20 / do-not-run-live.
   Answer: **run the capped 6-scenario subset**.

Both answers were given in-session by the operator. No authorization
was assumed, pre-existing, or carried over from earlier milestones.

## Scope actually used

- Downloads: `ollama pull llama3.2:1b` (~1.3GB) and `llama3.2:3b`
  (~2GB) only. No other models installed, removed, or modified.
- Live calls: 44 Muse Spark calls total — 37 for the authorized
  6-scenario x 5-turn subset plus 7 for one verification re-run of
  outlook-startup (needed to confirm a safety-relevant check fix).
  Synthetic fixture content only; no screenshots transmitted; no
  operator data.
- Everything else in M018 (~1,500 local calls) ran against loopback
  Ollama under `FIELDROOK_OFFLINE=1`.

## M019 standing

No cloud calls and no model downloads are planned for M019. If either
becomes necessary, a new explicit authorization must be obtained first:
this record authorizes nothing going forward.
