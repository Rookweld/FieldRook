# M031 – First Contact (FieldRook v0.6.0-rc.2)

**Human acceptance test, not a synthetic unit test.** Use the published ZIP,
not `C:\dev\FieldRook_EvidenceTrials`. Do not upload customer data, confidential
screenshots or production machine logs. No need for real faults to begin.

## Preparation on Fury

1. `ollama list` – confirm `qwen3:4b` is already installed.
2. `Invoke-RestMethod http://127.0.0.1:11434/api/tags` – confirm Ollama API.
3. Download from
   https://github.com/Rookweld/FieldRook/releases/tag/v0.6.0-rc.2
4. Verify ZIP SHA-256:
   `2398f20d1cf45e0f36cc380cdbfd0fc8d502dece4cfa04220830827e43ead87f`.
5. Extract everything to `C:\FieldRook\rc2\FieldRook-0.6.0-rc.2\`
   (adjust path if preferred).

Launch the **WPF executable** with this configuration in the same PowerShell
session (the child backend inherits its environment):

```powershell
$env:FIELDROOK_LOCAL_MODEL_URL = "http://127.0.0.1:11434/v1"
$env:FIELDROOK_LOCAL_MODEL_NAME = "qwen3:4b"
$env:FIELDROOK_LOCAL_API = "auto"
$env:FIELDROOK_LOCAL_THINK = "auto"
$env:FIELDROOK_MODEL_PROVIDER = "local"
$env:FIELDROOK_LOCAL_MODEL_VISION = "0"
$env:FIELDROOK_LOCAL_MODEL_TOOLS = "0"
& "C:\FieldRook\rc2\FieldRook-0.6.0-rc.2\FieldRook.exe"
```

If the application does not launch, gather a screenshot and the app's log
in `%LOCALAPPDATA%\FieldRook\logs` (redact sensitive information).
The published app is unsigned and requires Edge WebView2 Runtime.

## Case 001: remote Excel from Teams

- Choose **Application problem** or paste the following in **Problem description**:
  `M031 synthetic technician test. A user on another Windows 11 computer
  can open Excel files saved locally, but opening Excel files through
  Microsoft Teams produces an access denied error. The issue began this
  morning. No machine diagnostics have been collected yet.`
- **Affected computer:** `Another computer`.
- **Suspected service:** `No specific service`.
- No screenshot or Collector ZIP for the initial run.
- Expand **Advanced: fixture mode, provider (development and demos)**.
- `Force fixture data` unchecked; **Inference provider:** `local`.
- Press **Investigate**.
- Press **Open Guide**, verify **Inference provider** is `local`.
- Press **Test local connection**: expect `Reachable via ollama`, model
  answer and latency (if unreachable, report text; do not silently switch).
- Inspect **Questions for you**, **Hypotheses**, **Recommended next step**,
  **Current understanding**, evidence list and any fallback warnings.
- Under **Talk to FieldRook**, choose `Observation` and send:
  `Synthetic test update: a second user can open the same Teams file.
  The affected user can open local Excel files. No additional host
  measurements are available.`
- Check if the new response revises hypotheses and does NOT fabricate
  local measurements from Fury.

## Case 002: cancellation and resume

- Press **New investigation**.
- Select **Another computer**, `local`, no screenshot or forced fixtures.
- Start with `Synthetic test: a remote Windows laptop intermittently
  loses VPN connectivity; no host readings are currently available.`
- Under **Talk to FieldRook**, send an observation.
- While the model is working, press **Cancel this round**.
- Record whether the UI changes to `Cancellation requested` and whether
  the case can be resumed with prior evidence and history intact.
- If the model returns before the button can be clicked, report that
  honestly; do not assume cancellation failed.

## Capture only the following

| Observation | Your notes |
| --- | --- |
| WPF startup / UI clarity | |
| Connection test outcome and latency | |
| Model + processing location shown | |
| Remote-target isolation (no Fury evidence) | |
| Useful first question? | |
| Hypotheses supported, or fabricated? | |
| Did follow-up observations change the assessment? | |
| Cancel/resume behavior | |
| Any confusing wording, crashes or timeouts? | |

Send screenshots (with personal/customer details removed), error text,
and a quick summary back to the M033 chat. These M031 observations
become human acceptance criteria for the later M032 gauntlet.
