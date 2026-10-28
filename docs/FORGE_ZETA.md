# FORGE ZETA validation report (lead-executed, independent of builders)

Branch: `forge/integration` at `68b42bd`. All probes ran against an
isolated stack (backend :8123 + vite :4173, `FIELDROOK_OFFLINE=1`,
fixture diagnostics, simulated model, throwaway DB). Operator :8000
stack untouched. No cloud calls, no model downloads.

ZETA-as-designed (separate agent) was unavailable: workflow isolation
and `subagent_spawn` worktree isolation both fail in this session
(see ledger Phase B note). The lead therefore executed this checklist
directly against the merged product, trusting no builder claim without
a live observation.

## Secret scan (gitleaks unavailable -> verified grep fallback)

- `git diff master...forge/integration` scanned for key blocks, token
  prefixes (`ghp_`, `xox`, `AIza`, `sk-`), private keys, and
  `api_key/secret/password` assignments.
- Hits: only synthetic redaction fixtures (`hunter2`, `abc123`) and a
  `model_api_key=None` default. No real secrets.
- No `.env`/credentials files tracked; `.env` paths git-ignored.
- Worktree clean except preserved `.tmp-test/` scratch.

## Live adversarial probes: 17/17 (`C:\tmp\fr-forge-lead\zeta_probes.py`)

| probe | result |
|---|---|
| `/api/status` simulated mode | PASS |
| remote-target investigation start | PASS |
| committed `sample_basic.zip` imports (HTTP 200) | PASS |
| import keeps case target (`remote`) | PASS |
| evidence attribution (10 items, `collector:` source, package_id provenance) | PASS |
| no-consent import rejected (400), atomic | PASS |
| duplicate package rejected (409), atomic | PASS |
| tampered bytes rejected (422), atomic | PASS |
| traversal member (`../../zeta-evil.txt`) rejected (422), atomic | PASS |
| unknown tool manifest rejected (422), contained | PASS |
| references endpoint 200 (4 passages) | PASS |
| injection-laden problem -> quoted excerpts + disclaimer only | PASS |
| markdown export carries collector provenance + package id | PASS |

## Acceptance demo (real UI, `C:\tmp\fr-forge-lead\forge-demo.mjs`)

1. Intake shows the collector card beside screenshot input
   (`demo-1-intake-collector.png`).
2. DNS investigation renders the workspace + 4 `ref-dns-triage`
   citation chips, display-only (`demo-2-citations.png`).
3. `sample_basic.zip` imports through the UI with consent; Evidence
   tab moves 2 -> 12 (`demo-3-imported.png`).
4. Evidence view: 12 items, 6 categories
   (`demo-4-evidence.png`).
5. Markdown export verified in probes (step above).

Copies committed under `docs/assets/fieldrook-forge-*.png`.

## Regression gates (same commit)

- Backend pytest: **569 passed** (offline flag OFF, CI parity).
- Playwright E2E: **39/39** (7 forge + 32 legacy, all isolated).
- Diagnostic Gauntlet: **37/37**, exit 0.
- `tsc --noEmit` + `vite build`: clean.
- 14→18 tool count assertions updated with real tool names; legacy
  E2E selectors scoped to `.view-panel` after the dock legitimately
  duplicated controls (same capabilities, no deletions).

## Residual risks / not validated

- True-CPU interactivity FAIL stands from M018/M019 (~25-33s triage).
- No real second-laptop collector run; package provenance is
  format-verified, not field-verified on foreign hardware.
- `windows_net.py:1-129` / `windows_tasks.py:130-319` live bodies
  still not individually opened by the lead (BETA-owned).
- `.tmp-test/` locked scratch remains (orphaned worker lock).
