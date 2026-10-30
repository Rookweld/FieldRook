# FieldRook — the technician's instrument (M026 README draft)

> DRAFT for review. Do not publish without explicit authorization.
> When approved, this replaces `README.md` and the referenced shots
> ship under `docs/assets/m026/`. Every claim below traces to
> `docs/M026_DELIVERY.md`.

---

<p align="center">
  <img src="docs/assets/m026/launchpad-native.png" alt="FieldRook native Windows app on the SIGNALFORGE launchpad" width="720">
</p>

<h1 align="center">FieldRook</h1>
<p align="center"><strong>Diagnose. Verify. Resolve.</strong></p>

FieldRook is an evidence-driven Windows troubleshooting assistant. It
collects read-only diagnostics from the affected machine, ties every
conclusion to measurements it actually took, and refuses to guess when
evidence is missing. M026 delivers it as a genuine native Windows
workstation with the SIGNALFORGE visual system and a living,
motion-tunable interface.

## Principles

1. **Diagnose** — read-only tools and Collector packages gather facts;
   hypotheses stay labeled until measured.
2. **Verify** — re-checks, baselines, and before/after criteria decide
   whether a fix worked. No verification, no "resolved".
3. **Resolve** — interventions run through propose → approve → execute
   with single-use tokens, and only against the machine that was
   measured.

## Evidence-driven troubleshooting

Each investigation keeps cited evidence records with provenance (tool,
host, time), observations, uncertainties, and coverage. Imported
Collector evidence describes *another* computer: FieldRook never
re-measures it from your host and blocks wrong-machine actions with an
honest error. Simulated and fixture modes are always labeled as such —
ornamental interface motion is never presented as telemetry.

## The native Windows app

- Real window: minimize/maximize/restore/close, taskbar presence,
  DPI-aware, resizable down to narrow laptop layouts.
- Self-contained portable build: no Python or Node install required.
  The only prerequisite is the evergreen WebView2 Runtime.
- The shell spawns the backend as an owned child process
  (loopback-only), health-checks a desktop-identity status field, and
  reaps only what it spawned on close. No orphans.
- Single-instance with a friendly second-launch dialog; native
  file-open/save dialogs; drag-and-drop `.zip` Collector import with
  explicit sharing consent.
- Investigations persist across restarts in a per-user data dir.

## Collector workflow

1. Run the portable `FieldRook-Collector.exe` on the affected machine
   (authorized, read-only categories).
2. It writes a signed `.zip` package after a consent screen.
3. Import it at intake, mid-investigation, or by dropping it on the app
   window. Validation is atomic: any failure rejects the whole import.
4. Imported evidence is never executed and never re-measured from
   your host.

## Local AI vs cloud AI

- **Simulated** (default): deterministic analysis, no model calls.
- **Local**: optional on-machine model over localhost. Nothing
  auto-downloads; speed depends on your hardware.
- **Cloud (Meta)**: explicit live-model calls carrying only the current
  redacted investigation context, behind sharing consent. Switching a
  case with evidence to cloud needs explicit confirmation.

Screenshots require the sharing-consent box and are never stored —
only metadata is kept.

## Security and privacy

- Loopback-only backend; unauthorized origins rejected; typed,
  allowlisted native bridge (no unrestricted JS-to-native calls);
  path-traversal and non-loopback bridge targets rejected.
- Approval/execution separation for every corrective action.
- No live credentials or operator data in the portable build (release
  gates include a secrets sweep of the bundle).
- Code is unsigned (no signing authorized); checksums ship as
  `SHA256SUMS.txt` + `BOM.txt` with build provenance.

## Feature tour (all working, all tested)

| Shot | What it proves |
|---|---|
| Launchpad (above) | Real recent cases, runtime/provider status, New + Import actions |
| [Workbench](docs/assets/m026/workbench-case.png) | Problem, next action, hypotheses, evidence, notes, guide, resolution |
| [Evidence](docs/assets/m026/evidence.png) | Inspector with provenance + timeline |
| [Import](docs/assets/m026/import.png) | Collector package adopted into the open case |
| [Settings](docs/assets/m026/settings-motion.png) | Provider + Alive/Quiet/Off motion preference |

Demo video: `docs/assets/m026/demo-journey.webm` — one real
launchpad → investigate → evidence → recents pass (UI capture of the
same build the shell hosts).

## Honest limitations

- Local-AI triage speed is hardware-bound (tens of seconds on the
  default profile); no interactivity is promised during runs.
- Elevated Collector categories are excluded by design.
- Second-instance detection keys on the desktop identity; a foreign
  non-desktop listener on :8000 takes the discovery path (unit-covered,
  not exercised live).
- Multi-machine rollout, upgrades, and AV acceptance are unvalidated.
- The WebView2-absent path is code-reviewed, not run live (the runtime
  is present on all test machines).

## Download / build

No public download yet — release pending review. To build the portable
app from source on Windows (Node + pnpm, Python 3.12+, .NET 10 SDK):

```powershell
# From a clean checkout of m026/desktop-rebirth:
powershell -ExecutionPolicy Bypass -File packaging/desktop/build.ps1 -OutDir dist
powershell -ExecutionPolicy Bypass -File packaging/desktop/Build-Shell.ps1 -OutDir dist
# -> dist/FieldRook-0.5.0/FieldRook.exe  (+ .zip, SHA256SUMS.txt, BOM.txt)
```

Requires the WebView2 Runtime on the target machine (evergreen).
No signing is applied.

## Release status (M026 @ `c45ccc4`, v0.5.0)

| Gate | Result |
|---|---|
| Backend pytest | 684 passed, 4 skipped (env) |
| Playwright E2E | 47 / 47 |
| Diagnostic Gauntlet | 37 / 37 fixtures |
| .NET shell tests | 66 / 66 |
| Frozen-app smoke | window ops, single-instance, fenced shutdown, 0 orphans |
| User journey | intake → evidence → import → export → restart persistence |
| Motion/a11y | Alive/Quiet/Off + reduced-motion + keyboard + narrow layouts |
| Security | 11/11 live probes, loopback/origin/traversal guards, secrets sweep clean |
| Perf | cold ~8s, warm ~4–5s, idle ~1.2% CPU / ~385MB, close ~1.5s |

Full record: `docs/M026_DELIVERY.md`. Independent validation by the
ZETA waves (blocking findings fixed and re-verified, including a
remount bug that broke case adoption and a CSS cascade that kept the
tab strip transparent).

## Attribution

Built by **ROOKWELD** — FORGE. BUILD. IMAGINE.
FIELDROOK — DIAGNOSE. VERIFY. RESOLVE.
