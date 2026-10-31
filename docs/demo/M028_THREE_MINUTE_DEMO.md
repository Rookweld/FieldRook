# M028 — Three-minute demo: script, shots, and proof map

Status: shooting script (not recorded, not submitted). Target 2:50–2:58 plus
end-card buffer. Follows the M028 3-minute demo plan beats; every screen
action below was verified hands-on against commit `d892b83` + this branch.

## 1. Chosen scenario (READ FIRST — theme change vs the suggestion)

**Shipped scenario: "The FieldRook demo worker is down"** — a deterministic
fixture fault carried through the full arc: investigation → registered
diagnostic request → evidence + provenance → hypothesis / uncertainty →
technician action + measured verification → exported report. The before/after
is an actually recorded check pair (plan baseline evidence vs verification
evidence, rendered as `before 'failed' -> after 'failed'` criterion rows).

**The suggested "VPN connects but intranet/DNS fails" theme is NOT used.**
Fixture/data audit (all verified in code, 2026-10-31):

- `_FIXTURE_ADAPTERS` contains Wi-Fi (Up) and Ethernet (Disconnected) only —
  no VPN adapter exists, so "VPN connects" cannot be shown as a measurement.
- The simulated loop's DNS branch always issues one control query,
  `test_dns_resolution {hostname: example.com}`, which the fixture answers
  `succeeded: true` (`93.184.216.34`). No problem text routes a failing
  intranet lookup through the loop.
- `resolve_fixture_hostname` fails only for names outside
  `{example.com, localhost}`, but nothing in the deterministic path queries
  such a name. Narrating "intranet DNS fails" would therefore be assertion
  without evidence — exactly what FieldRook refuses to do.

Network coverage is not dropped: the new `network-lab.spec.ts` E2E pins the
adapters/addresses/DNS-config/DNS-test readings, the five-tool networking
allowlist, and the remote-target guard. The video keeps ONE case per the
golden rule.

Two naming facts the merge lead must keep straight:

- The DNS tool's registered name is **`test_dns_resolution`**, not
  `resolve_hostname` (see `backend/app/tools/registry.py` `REGISTRY` and
  `/api/tools`). The mission brief's `resolve_hostname` matches only the
  internal `resolve_hostname_live` / `resolve_fixture_hostname` helpers.
- `/api/tools` marks exactly five tools `family: "networking"`:
  `get_network_adapters`, `get_ip_config`, `get_dns_config`,
  `get_connections`, `test_dns_resolution`. No ping / traceroute / port scan
  exists under any name.

## 2. Recording environment (deterministic, isolated, sanitized)

Mirror the Playwright `webServer` block (`frontend/playwright.config.ts`):
backend on an isolated port (e.g. `:8123`, never the operator's `:8000`)
with a FRESH database, frontend with `FIELDROOK_API_PORT=8123`, fresh
browser profile (Launchpad shows "No investigations on record yet").

```powershell
$env:MODEL_API_KEY = ""
$env:FIELDROOK_OFFLINE = "1"
$env:FIELDROOK_FIXTURES = "always"
$env:FIELDROOK_FIXTURE_WORKER = "failing"
$env:FIELDROOK_DB_PATH = "<fresh-empty-dir>\demo.db"
$env:FIELDROOK_DEMO_STATE = "<fresh-empty-dir>\demo-state"
$env:FIELDROOK_API_PORT = "8123"
```

Why each: empty key + `FIELDROOK_OFFLINE=1` forces the simulated provider
(code: `select_provider`, `MetaModelProvider.chat` refuses offline); fixtures
`always` + worker `failing` fixes every reading below; fresh DB keeps
evidence ids `ev-1…` and a clean Launchpad. Window 1920×1080 (≥1280×720
per M028.A); OS reduced-motion ON is recommended so ambient cues sit still.
Nothing on screen is a secret: fixture MACs/IPs only, no keys, no operator
paths. Intake text (paste-ready):

> `The FieldRook demo worker is down.`

Intake settings: Affected computer = This computer; Advanced → Force
fixture data ON; Inference provider = auto. Expected deterministic result
(probe-verified): status `complete`, mode `simulated`, model
`fieldrook-simulated-001`; `ev-1` = `demo_worker` via
`get_demo_worker_health`, source `tool:get_demo_worker_health:fixture`,
`status: failed`, detail `Simulated fault (mode=failing).`; one proposal
`recover_demo_worker → demo-worker`, status `AWAITING_APPROVAL` (shown, never
approved in this video).

## 3. Timestamped script (narration ≈ 400 words, first person)

### 00:00–00:14 — Hook
[Launchpad hero: BE CURIOUS. BE CERTAIN. Overlay: REAL APP / DEMO FIXTURES]
"When a Windows computer breaks, technicians get a symptom, not an
explanation. Logs, services, and network state live in different tools. I
built FieldRook to bring them together — without asking an AI to guess."

### 00:14–00:32 — Start one case
[Click "+ New investigation ↗" → Workbench intake. Paste the problem text.
Tick "Force fixture data". Click Investigate. Cursor rests on the THIS PC
badge as the case opens.]
"I start with a user report. FieldRook opens a case, records WHICH computer
we're investigating — this badge stays with every reading — and tracks what
has actually been measured. Fixture data is on, and the app says so."

### 00:32–01:02 — Tool boundary + evidence
[Findings: SIMULATED and FIXTURES badges. Evidence tab → "Demo worker (1)".
Open ev-1: category, `tool:get_demo_worker_health:fixture`, timestamp,
`status: failed`. Scroll the case timeline.]
"The AI can request only registered, schema-validated diagnostics — this one
is `get_demo_worker_health`. Each call is bounded and logged; it cannot
invent shell commands. The response becomes timestamped evidence, not a
permission slip. Re-checks would add new readings, never rewrite this one."

### 01:02–01:24 — Hypothesis, uncertainty, human control
[Diagnosis: OBSERVED fact citing ev-1; INFERRED causes with likelihoods;
UNVERIFIED uncertainties. Resolve tab: proposal card
`recover_demo_worker → demo-worker`, AWAITING_APPROVAL. Do NOT approve.]
"The model states facts, hypotheses, and open questions separately — and
names what it can't prove. It proposes exactly one registered recovery. Note
the status: awaiting approval. Nothing runs until a human says so."

### 01:24–01:54 — Technician action + measured verification
[Resolve tab → New resolution plan → Use demo-worker recovery template
(2 criteria) → Create resolution plan → DRAFT → Capture pre-fix baseline →
BASELINED → type "Restarted the worker by hand." → Record manual fix →
INTERVENED + MANUAL CLAIM → Confirm Fix → NOT_RESOLVED. Linger on the
criterion rows: `before 'failed' -> after 'failed'`.]
"I record the intervention as a manual claim — a claim proves nothing. Then
FieldRook re-measures. The worker still reports failed, so the honest
outcome is NOT resolved. A claimed fix that measurement disproves — caught,
on the record."

### 01:54–02:20 — Exported report
[Report export → Download Markdown. Open the file; show §4 Collected
evidence (ev-1 with source), §10 Final verified outcome (NOT_RESOLVED),
§15 Resolution plans (criterion rows with before/after evidence ids),
§17 hypotheses. Scroll, don't speed-read.]
"The ticket-ready report carries the evidence, the before-and-after
measurements, the approval trail, and the verified outcome. No screenshot
bytes, no keys, no tokens — exports can't leak them by construction."

### 02:20–02:45 — Technical proof: tool-calling boundary + verification
[Split overlay, all real: (1) `/api/tools` JSON in a browser tab —
registered names only; (2) terminal: `prepare_call("rm -rf …")` equivalent
rejected — show the `Unknown tool` error from the backend test run, not a
live shell; (3) freeze-frame the criterion row `before 'failed' ->
after 'failed'`. Overlay: SIMULATED MODEL — NO LIVE INFERENCE SHOWN.]
"Two guarantees, both checkable. One: unknown tools and bad arguments are
rejected before anything executes — the registry in
`backend/app/tools/registry.py` is the whole allowlist. Two: verification
re-reads state through the same registered tools and grades criteria from
fresh evidence ids — never from the model's word."

### 02:45–02:58 — Take-home + end card
[Workbench hero with the case badge row. Overlay: test counts from the
actual validation run — fill at record time, never invent. End card:
FieldRook / Diagnose. Verify. Resolve. + GitHub URL.]
"Local FastAPI engine, typed tool registry, audit trails, isolated tests.
Open source, available now. FieldRook. Less guessing. More evidence."

## 4. Shot list (one sequence, no re-takes needed if env is fresh)

1. Launchpad hero + badges (SIMULATED MODEL / FIXTURES ONLY in top bar).
2. Intake: pasted problem, This computer, Force fixture data ticked, Investigate.
3. Findings: FIXTURES + SIMULATED badges, THIS PC context badge.
4. Evidence tab: "Demo worker (1)", ev-1 card (source line, timestamp, status).
5. Case timeline (Evidence tab bottom).
6. Diagnosis: OBSERVED / INFERRED / UNVERIFIED blocks with ev-1 chips.
7. Resolve tab: proposal card AWAITING_APPROVAL (untouched).
8. Plan lifecycle: DRAFT → BASELINED → INTERVENED/MANUAL CLAIM → NOT_RESOLVED.
9. Criterion rows: fail `before 'failed' -> after 'failed'`; pass heartbeat `1.2 lt 10`.
10. Markdown export: §§ 4, 10, 15, 17.
11. Proof overlay: `/api/tools` JSON + `Unknown tool` rejection + criterion freeze-frame.
12. End card.

## 5. Actual UI vs simulation

| Shot | Actual running UI | Simulated / fixture |
|---|---|---|
| 1–10 | Yes: real SIGNALFORGE + engine on an isolated backend | Readings are deterministic fixtures, labeled FIXTURES in-app |
| 4, 9 | Yes: real evidence cards, criterion grading | Health `failed` is the `FIELDROOK_FIXTURE_WORKER=failing` fault |
| 7 | Yes: real proposal lifecycle state | Recovery is proposed, never executed on camera |
| 11 (1) | Yes: live `/api/tools` response | — |
| 11 (2) | Test output, labeled as such | Not a live attack; a backend rejection test |
| 11 (3) | Yes: freeze-frame of shot 9 | — |
| Voiceover "the model…" | — | SIMULATED analysis (`fieldrook-simulated-001`); never call it live |

Per the demo plan: where the script says "the model", the footage badge
says SIMULATED, and §6 states the live-Meta proof status explicitly.

## 6. Meta tool-calling boundary + independent verification (the 25s proof)

What the boundary is (code refs for the reviewer, not for narration):

- The model receives ONLY `tool_schemas()` built from `REGISTRY`
  (`loop.py: tools_for_target`, scoped further by diagnostic target).
- Every requested call passes `prepare_call`: unknown name → `ToolCallError`
  ("Unknown tool"); args validated by strict per-tool Pydantic models
  (`extra="forbid"`); nothing executes before validation.
- Execution is bounded (`execute_prepared`: per-call timeout, 12 000-char
  truncation) and every result ships as data with an `evidence_id` the
  model must cite — citations to anything else fail validation
  (`validate_assessment_output`).
- The model can only *propose* the single registered action
  `recover_demo_worker` on `demo-worker`, and only when
  `get_demo_worker_health` evidence shows failure; proposing never executes
  (approval + execution + independent `verify_healthy` re-read are separate
  human-gated steps).
- Verification is independent: plan criteria re-run registered tools and
  grade `before_evidence_id` vs `after_evidence_id` readings
  (`resolutions/service.py`); the video's NOT_RESOLVED comes from that
  grading, not from any model statement.

**Live-Meta proof status: MISSING — do not claim live inference.** No
`MODEL_API_KEY` exists in this environment (presence-checked 2026-10-31,
value never read), so the separately-labeled live-provider run was not
performed. If a live run is later captured, attach its redacted transcript
(response id, timestamp, allowlisted tool names) to the manifest below and
re-record §3's 02:20–02:45 beat only.

## 7. Shot-to-evidence manifest

Deterministic values (probe-verified 2026-10-31, backend `d892b83`):

- Source build commit: `<worktree HEAD at record time>`
- Device identity: fixture host (MACs `AA-BB-CC-DD-EE-0x`, LAN `192.168.1.x`)
- Model mode: simulated / `fieldrook-simulated-001` (badged in every shot)
- Live Meta proof: NONE — see §6
- Registered tool, args, evidence: `get_demo_worker_health`, `{}`, `ev-1`
  (`tool:get_demo_worker_health:fixture`)
- Plan criteria: `(get_demo_worker_health, status, eq, healthy)`,
  `(get_demo_worker_health, heartbeat_age_s, lt, 10)`
- Before/after: baseline `ev-N` vs verification `ev-N+1`;
  crit-1 fail `before 'failed' -> after 'failed'`; crit-2 pass `1.2 lt 10`
- Verification outcome: `NOT_RESOLVED`
- Collector package: none used in this scenario (no remote-work claim made)

Fill at record/export time:

- Video export length, codec, exact hash, playback check:
- Submission URL + accepted timestamp (only after actual submit):

## 8. E2E coverage behind this demo

- `frontend/tests/e2e/evidence-lens.spec.ts` (new, M028.D): deterministic
  record order + provenance, original-vs-recheck UNCHANGED comparison with
  `refresh_of` linkage, contradiction citations with chip drill-through,
  refresh JSON contract, export §14 linkage.
- `frontend/tests/e2e/network-lab.spec.ts` (new, M028.D): observed
  adapters/addresses/DNS readings with tool/source labels, passive-config
  vs active-test separation, five-tool networking allowlist pin, no
  ping/traceroute UI, remote-target re-check withdrawal + API 409.
- Pre-existing `resolution.spec.ts` covers the §3 plan lifecycle end to end
  (DRAFT → BASELINED → INTERVENED → NOT_RESOLVED) and must stay green.
