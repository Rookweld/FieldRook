# M040 — Real Incident Evidence, Question Lifecycle & Multi-Layer Diagnostics

**Date:** 2026-11-25 (Europe/Stockholm)
**Branch:** `m040/real-incident-evidence`, based on `m039/first-install-acceptance` (`8315b16`)
**Release:** published `v0.6.0-rc.4` remains **unchanged**
**Scope:** FieldRook local-model reasoning and technician question lifecycle (no UI changes or installer rebuild).

## Motivation — an actual incident, not a synthetic failure

On 2026-11-24 the Nullfeather Bridge on Fury repeatedly flashed ONLINE and exited. Technician-led fault isolation found *three consecutive independent blockers*:

1. Windows PowerShell 5.1 loaded the PowerShell 7 `Microsoft.PowerShell.Security` module, preventing `ConvertTo-SecureString` from loading the DPAPI secret.
2. `tunnel-client` looked for a YAML profile under `~/.config/tunnel-client` while the existing profile was under `%APPDATA%\tunnel-client`.
3. The local health HTTP listener failed binding port **8080**, which was inside Windows' reported excluded TCP range **8019–8118**. Port 18080 accepted a bind.

After a technician corrected these problems, health and readiness returned HTTP 200. A first retrospective replay through FieldRook (2026-11-24) found **repeated already-answered questions**, generic firewall/permission guesses for 8080, and an initial **Qwen3 4B triage timeout**. Model answers were not consistently the same as a grounded diagnosis. The original case and transcripts remain under the ignored `backend/eval/results/real-bridge-20261124/`.

## M040 changes

### 1. Evidence-linked, reported-only Windows port correlation

New `app/analysis/technical_signals.py` detects a **precise pattern** in a *single* technician report: TCP listener bind denied, a reported Windows excluded TCP port range, and the failed port mathematically falling inside that range.

- Model receives a short diagnostic hint suggesting a Windows **port reservation** ahead of unsupported generic firewall or conflicting-process guesses.
- The assessment displays the relation as **technician-reported**, explicitly **not** as FieldRook's independent host measurement or proof of root cause.
- Invalid ranges, no bind denial, connection refusal and ranges unrelated to the failed port never trigger the correlation.
- This module runs no commands, mutates no OS settings and does not authorize remediation.

### 2. Multi-stage startup blockers in chronological context

A bounded set of explicit error categories tracks reports of module import errors, configuration/profile lookup failures and TCP listener bind denials. When multiple different stages have been reported, FieldRook shows an ordered summary. Previous blockers remain historical context: **not all are asserted to still be active after the technician resolves them**. The summary is never presented as a measured host diagnostic.

The local reassessment prompt also receives a concise, report-only chronological hint so the model does not prematurely collapse separate startup blockers into one hypothesis.

### 3. Already-answered / stale question lifecycle

`app/analysis/assist.py` now suppresses or retires selected questions when explicit evidence is already present:

- Known local/remote target does not require another generic target-selection question.
- Yes/no questions substantially covered by a **single** user report (including prompts wrapped in the deterministic fallback prefix) are withheld; open-ended why/how questions are not inferred from keyword overlap.
- Requests for exact error text are retired only after a distinctive error/code is supplied.
- A question about a missing profile path remains open until a technician says the client **successfully reads** the profile; merely noting the file exists is insufficient.
- Startup permission/path verification questions can retire once the technician reports the relevant executable actually launched.
- Settled questions remain in history with a reason. No technician answer or evidence is deleted.

## Verification

### Automated tests

- `backend/tests/test_m040_real_incident.py` and `backend/tests/test_m040_followups.py` cover positive and negative examples, report-vs-measurement provenance, overlapping port arithmetic, question lifecycle and actual local-pipeline isolation with a mocked transport.
- Combined final targeted regression, including `test_local_tasks.py`, `test_assist.py`, `test_information_gain.py`, and `test_evidence_integrity.py`: **195 passed, 1 deprecation warning, 0 failed** in 10.96 s.

### REAL local-model replay (actual FieldRook API, no model mocks)

A separate clean replay of the **same historical, technician-reported** Fury incident was run with **Qwen3:8B via local Ollama**, using the real FastAPI `/api/investigations` and `/turn` endpoints and **a fresh isolated SQLite database**:

- `backend/eval/results/m040-final-20261125/run_real_bridge.py`
- `backend/eval/results/m040-final-20261125/qwen3-8b/` (five JSON turn snapshots, a final case record and progress report).
- Inference was live local (`local/qwen3:8b`), no fixture mode, remote target, **0 host tool calls**, no model-suggested corrective actions executed.
- The intake round generated **no already-answered questions**; the end-of-case state also had **0 open questions** in this one run.
- After the technician supplied the PowerShell and YAML evidence, a reported-only multi-stage failure summary was displayed.
- After the excluded-range data appeared, the assessment explicitly showed that 8080 falls inside 8019–8118, and the model suggested checking whether **Windows reserves port 8080**. It still included an alternative possibility of another process, so the conclusion is **not** a uniquely proven root cause.
- The final response showed recovery reported by the technician, and suggested monitoring for recurrence. **Stage was REASSESSING**; this remains an investigation, not FieldRook-verified technical resolution.
- Initial local-model intake took approximately **5.9 s** in this warmed replay; do **not** compare it directly with the previous 50.3 s intake (different model-cache state and random inference). No generalized latency reduction is claimed.

## Boundaries and remaining risks

- These were technician-provided observations about a *real incident*, replayed retrospectively; **FieldRook did not autonomously inspect or fix the original live bridge**.
- Correlations are narrow and mathematical; reports are untrusted as independent evidence. No sensitive log contents, API keys or credentials are included in committed tests.
- Qwen3 4B's earlier **cold-start triage timeout is not fixed** in this milestone; retry timing, model cold-start lifecycle and deterministic fallback visibility need a separate targeted performance investigation.
- The published rc.4 release, installer, GUI and customer's existing case data were not modified.
- No broad end-to-end GUI test, fresh-machine installer test or longitudinal external technician validation was claimed.
- The five-turn live replay is **one sample**, not statistically significant model-quality evidence.

## Next milestone recommendation

**M041 – Cold-Start Reliability & Real User Trial:** instrument model loading and timeout budgets; add a bounded, explicitly labelled recovery for local triage failures; evaluate the same 2–3 real cases on multiple machines and collect independent technician judgements. Keep `observe` as default and human approval for system changes.
