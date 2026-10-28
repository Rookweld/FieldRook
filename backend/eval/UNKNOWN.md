# Unknown-problem evaluation (M016)

`eval/unknown_problems.py` + `eval/run_unknown.py`. Offline, hermetic,
deterministic: temp database, fixture tools, simulated provider, no key.

## What it proves

The main gauntlet tests prepared scenarios. This suite tests **adaptability**:
unfamiliar reports outside the fixture catalog, where the honest behaviors
are clarifying questions, remote-target restraint, hypothesis revision, and
graceful blocking — not confident diagnoses.

## The twelve cases

| # | Case | Asserts |
| - | ---- | ------- |
| 1 | `unknown-office-error-code` | `0x80070005` decoded via `interpret_error_code`; hypotheses + plan exist; simulated likelihoods never high; citations valid |
| 2 | `teams-file-access` | Remote: zero tool calls, zero host evidence, no automated steps; stage CLARIFYING |
| 3 | `printer-other-laptop` | Remote guards hold; missing evidence names the machine gap |
| 4 | `vpn-intermittent` | Network tools used; no duplicate (tool,args) calls; initial budget ≤ 8; citations valid |
| 5 | `laptop-slow` | Uncertainty communicated; bounded triage; plan exists |
| 6 | `app-freezes` | Completes with zero verified claims; offers a next direction |
| 7 | `unknown-dialog-screenshot` | Screenshot metadata-only (no bytes); consent acknowledged; questions asked |
| 8 | `needs-clarifying-question` | Unknown target asks for the affected machine first; CLARIFYING |
| 9 | `no-tool-applies` | Out-of-domain report: ≤ 3 tools, manual guidance, no proposal, no high likelihood |
| 10 | `hypothesis-revision` | Contradicting observation + technician judgment retires a hypothesis; history preserved; later rounds never override the judgment |
| 11 | `cannot-perform-test` | Every step impossible → BLOCKED with reason; blocked outcomes kept |
| 12 | `verified-recovery-not-assumed` | Manual "I fixed it" claim is measured against a failing criterion → NOT_RESOLVED |

Every case also validates **citation integrity**: all evidence references in
facts, causes, runbook steps, hypotheses, and plan steps must resolve to
collected evidence.

## Results

- 2026-10-28: **12/12 passed** (`eval/results/unknown-*.json`), exit 0.
- Live-model tier: not run in M016 (no authorized Meta calls). The
  simulated tier validates application behavior — provider honesty,
  boundaries, and workflow — not model quality. Live-model adaptability
  (Muse Spark vs local models on held-out cases) is M018 scope.
