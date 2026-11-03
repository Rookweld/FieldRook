# M029 Meta Muse Spark live proof — status: BLOCKED (no API key available)

Date: 2026-10-31. Branch: m029/prove-polish-record (local only).

## What was checked (boolean only, no values)

- `MODEL_API_KEY` environment variable: **absent** (empty-or-unset check; value never read, printed, or logged).
- No `.env` file in the worktree; no key material in repo, logs, or screenshots.
- No scraping of any kind was performed: no Muse Code auth, browser storage,
  key vault, or account access. No secrets were requested in chat.

## Consequence

No live Meta Muse Spark inference was performed or claimed. All M028/M029 demo
material stays honestly labeled **SIMULATED** (fixtures: `fieldrook-simulated-001`).
The video script keeps SIMULATED labels throughout; section 6 of
`docs/demo/M028_THREE_MINUTE_DEMO.md` records the same.

## Single action required (owner)

1. Create an API key at Meta Model API dashboard > API Keys.
2. In a FRESH isolated shell (never in git, logs, or screenshots), run ONE bounded
   investigation with the key supplied in-process only:

```powershell
$env:MODEL_API_KEY='<paste-key-here>'   # process env only; close the shell after
$env:FIELDROOK_FIXTURES='always'
$env:FIELDROOK_DB_PATH='<empty-temp-dir>\m29-live.db'
# backend on an owned free port, provider explicitly meta, OFFLINE disabled,
# synthetic fixture data only, one investigation, no loops (mind rate limits)
```

3. Verify and report back (redacted): provider/model badge reads LIVE (not
   simulated), response metadata + timestamp, actual registered tool calls with
   bounded args, validated evidence IDs cited in the result, and failed/uncertain
   outcomes. Mask the model name if required by your key agreement.

## What the live run must prove (assistant checklist for the follow-up)

- A live Meta model called an allowlisted diagnostic with schema-validated args.
- It received real (fixture) tool results and cited evidence by ID.
- Actual model inference is distinguished from synthetic diagnostic measurements.
- Target guards (409/422), consent, and audit behavior unchanged.
- If the provider bridge fails: diagnose narrowly, keep safety gates intact,
  never silently fall back and claim Meta success.

## Fallbacks (not equivalent)

- A verified local Meta open-weight model run may be used as supplementary
  material but must never be presented as live hosted Muse Spark inference.
- If no live run is possible, the submission keeps the SIMULATED label and this
  file stays the proof-of-blocker record.
