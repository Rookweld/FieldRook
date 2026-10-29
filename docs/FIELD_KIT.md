# FieldRook Field Kit — technician guide (M025)

The Field Kit is the standalone way to run FieldRook: a Collector
executable that gathers read-only diagnostics on an affected computer,
plus a desktop app (single local server + browser UI) where the
technician investigates. No Python, Node, or admin rights required to
use either half.

Scope note: this guide ships with the first-run track (GAMMA). It
describes the M025 runtime contract (`docs/M025_CONTRACTS.md`); the
integrated build is assembled by the lead and clean-machine runs are
validated by ZETA. Nothing below claims a clean-machine result — where
a behavior is contract-specified rather than observed here, it says so.

## Install

1. Unpack the Field Kit directory to any writable folder (for example
   `Documents\FieldRook` or a USB stick). No installer, no admin prompt.
2. Start the launcher. It starts one local server, opens the browser UI,
   and owns shutdown: stopping the launcher stops only its own
   processes.
3. The server binds loopback only — `127.0.0.1:8000` by default,
   overridable with `FIELDROOK_PORT`. A non-loopback bind is refused at
   startup.
4. First launch opens the first-run guide (see below). Your data
   (investigations, imported packages, logs) lives under
   `%LOCALAPPDATA%\FieldRook`, never beside the executables and never
   in a developer checkout. Existing `FIELDROOK_DB_PATH` /
   `FIELDROOK_DEMO_STATE` overrides still work.
5. Only one copy runs at a time: a second launch reports "already
   running" instead of failing obscurely.

Release hygiene, carried over from M020: the artifacts contain no API
keys, no `.env`, no personal investigation data, and no bundled model.
Builds are unsigned (no code signing authorized) — expect the standard
Windows unknown-publisher prompt. Startup and shutdown errors are
shown on screen and logged to `%LOCALAPPDATA%\FieldRook\logs`.

## Remove

1. Stop the launcher (or the desktop app window) so the server and its
   demo worker exit.
2. Delete the unpacked Field Kit directory.
3. Optional: delete `%LOCALAPPDATA%\FieldRook` to drop all local state
   (database, imported packages, logs). Nothing was installed
   elsewhere — no services, no registry keys, no admin-leftovers.

## First run

The first visit opens a welcome card explaining what FieldRook
diagnoses, what "local target" means, Collector packages, providers,
cloud consent, and what works with no model. It is dismissible two
ways:

- **Start diagnosing** — closes the guide and remembers the choice
  (marker `fieldrook.first-run.v1` in browser local storage). The
  guide stays gone on later visits.
- **Dismiss for now** — closes it for this session only; it returns
  on the next visit.
- While dismissed, a small **First-run guide** button reopens it, and
  **Show on next visit** inside the guide clears the marker.

Read the header badges before your first investigation (same meanings
as `docs/FIRST_RUN.md`): `LIVE MODEL` / `SIMULATED MODEL` says who is
reasoning; `LIVE DIAGNOSTICS` / `FIXTURES ONLY` says whether this
machine can run real read-only diagnostics. Then run your first
investigation exactly as the First-Run Guide describes (Service lookup
on `wuauserv`, or a symptom in your own words).

Automated tests: the gate renders nothing when `navigator.webdriver`
is set (Playwright and similar), and it never traps focus or covers
the page, so the existing E2E suites — including
`forge-workstation.spec.ts` — pass unchanged with no test edits. The
marker key above is the only persisted state.

## Collector journey (steps 1–12)

The Collector is a console executable (`FieldRook-Collector.exe`, same
`collect|validate` CLI and exit codes as `python -m collector`). It is
stdlib-only and offline: it never transmits anything. Categories:
services, os, events, network, tasks, procs (see the consent screen
for exactly what each reads).

1. **Confirm authority.** You may collect only on a machine whose
   owner/user agreed. Collection is read-only, but it is still their
   machine.
2. **Bring the Collector.** Copy `FieldRook-Collector.exe` to the
   affected computer (USB stick or existing remote-file route). No
   install, no admin required; two categories (event log, scheduled
   tasks) merely report less without elevation and say so.
3. **Preview the consent screen.** Run `collect` without `--yes`
   first. It prints the per-category list — what is read, under which
   privilege flag — plus the privacy footer (redaction on this
   computer, hostname stored as hash + your label, full command lines
   never collected).
4. **Explain and get a yes.** Walk the owner through the screen. The
   `--yes` flag is your acknowledgement that this happened.
5. **Collect.** Re-run with `--yes --out package.zip`. Optional:
   `--hint LABEL` (your label for the machine — never its hostname),
   `--categories` for a subset, `--service NAME` for service details,
   `--note file.txt` to attach UTF-8 text (`.json`/`.txt`/`.md`/`.log`
   only). Exit 0 means the package was written; exit 2 means consent
   or usage was refused; exit 1 means the package could not be built.
6. **Read the warnings.** The end of the run prints per-category
   warnings (for example, a category that needs more privilege).
   Report them honestly — a truncated category is a fact about the
   evidence, not a failure to hide.
7. **Validate on the spot.** Run `validate package.zip`. `VALID`
   names the package id, entry count, and file count; `INVALID`
   explains why (exit 1). Never carry an invalid package forward.
8. **Carry the package back.** Move the .zip to your FieldRook
   workstation by whatever route you trust (USB, ticket attachment).
   It holds diagnostics, not secrets in the clear — secrets, emails,
   `DOMAIN\user`, OS usernames, and command lines were redacted or
   dropped at collection — but treat it as machine data regardless.
9. **Open or start an investigation** in the desktop app for the
   affected machine's problem.
10. **Import with consent.** Attach the .zip at intake or via the
    Collector import card, and check the sharing-consent box ("I am
    authorized to share this machine's diagnostics"). Without the box
    the import is refused; non-ZIP files are rejected client-side.
11. **Let validation finish.** The package is verified atomically —
    traversal, symlink/device, size caps (2MB per file, 20MB total,
    200 files), compression ratio, hash mismatches, and unlisted or
    missing members each reject the *whole* import with a
    machine-readable detail list and no partial ingest. On success the
    entries join the investigation as cited evidence with provenance
    (`package_id`, collector version, manifest hash, redaction
    counts). Nothing imported is ever executed.
12. **Respect the re-check boundary.** Imported evidence describes a
    computer this workstation cannot see, so it offers no Re-check
    button — the card points back to importing a fresh package. To
    update the picture, repeat from step 5 on the affected machine.

## Providers

FieldRook separates **inference provider** (where intelligence runs)
from **diagnostic target** (which computer the evidence describes).
Full reference: `docs/PROVIDERS.md`.

| Provider | Selected by | Processing | Vision | Tool calling |
| -------- | ----------- | ---------- | ------ | ------------ |
| `meta` | `MODEL_API_KEY` set (auto) or explicit | Meta cloud | yes | yes |
| `simulated` | no key, `FIELDROOK_OFFLINE=1`, or explicit | none | no | no |
| `local` | explicit only | this computer (loopback endpoint) | configurable | configurable |

- List live availability at `GET /api/providers` (static
  configuration; the endpoint never probes the network). The first-run
  guide shows the same status.
- Server default: `FIELDROOK_MODEL_PROVIDER=auto|meta|simulated|local`.
  Per investigation: the intake `provider` field or the Guide's
  provider switcher; the choice applies to the next round and past
  assessments keep their labels.
- **Local AI is optional.** FieldRook works fully without one, and
  nothing is downloaded automatically. Setup is an explicit
  OpenAI-compatible loopback URL (`FIELDROOK_LOCAL_MODEL_URL` plus
  model name, vision/tools flags defaulting off), over an existing
  Ollama install, with hardware checks and user-controlled
  install/remove. The URL must be loopback — anything else is refused
  before any request — and the cloud key is never sent to it.
- **No responsiveness promises.** A small CPU model runs a bounded
  task pipeline (triage / plan / reassess) instead of the full cloud
  call because the full call never completed on CPU (M016–M019
  measurement). Measured true-CPU triage for the default `qwen3:4b`
  profile is tens of seconds; larger models take longer. The in-app
  profile says so, and this guide makes no smaller claim.
- A provider that fails (timeout, bad output, unreachable endpoint)
  falls back to simulated analysis with an explicit warning — the
  round never hangs and never fabricates a result.
- The local connection test (`POST /api/providers/local/test`, one
  tiny capped completion) is user-triggered only; the Guide never
  polls or preloads models. A long turn can be cancelled mid-flight
  (~0.2s abort) with evidence kept and the investigation resumable.

## Offline capabilities

With no model and no network beyond localhost, all of this still
works:

- Live read-only diagnostics on the local target (or clearly labeled
  fixtures where the host cannot run them).
- Deterministic simulated analysis — labeled `SIMULATED MODEL`, never
  presented as model reasoning.
- Service lookup, investigations, turns, notes, and clarifying
  questions.
- Collector package validation and import.
- Knowledge library (local SQLite, deterministic in-process matching)
  and reference excerpts as quoted display blocks.
- Resolution plans, fix verification (`VERIFIED_RESOLVED` /
  `NOT_RESOLVED` / `INCONCLUSIVE`), and Markdown/JSON report export
  (operator-initiated downloads, never uploaded).

`FIELDROOK_OFFLINE=1` explicitly forbids all Meta model calls even if
a key is configured; switching *to* the cloud provider while an
investigation holds screenshots, evidence, or notes requires explicit
`confirm_cloud` authorization. Switching between simulated and local
needs no confirmation.

## Privacy and target isolation

Honest boundaries, each enforced in code (see `docs/FORGE_PRIVACY.md`
for the per-claim enforcement map):

- **Localhost only.** The API listens on loopback; the local model
  endpoint must be loopback; non-loopback binds are refused. The only
  traffic that ever leaves the machine is an explicit live-model call
  carrying the current redacted investigation context.
- **Local vs imported evidence never mix.** Local targets are
  measured on this machine; collector targets arrive as validated
  packages. Imported items carry provenance and a recollect hint
  instead of a Re-check button, and reverify requests on them become
  technician guidance naming the collector capability.
- **Consent gates.** Screenshots need `share_consent` and are never
  persisted (metadata only, labeled with the processing location).
  Package import needs `share_consent=true`. Cloud escalation needs
  an explicit user decision.
- **Minimization.** Raw hostnames never persist (`hostname_hash` plus
  an optional sanitized hint). Turn text is redacted before model
  contact; reference excerpts reach the model only as quoted blocks
  on user-role messages, never as system instructions; fabricated
  citations are dropped by output validation.
- **Residual risks, stated plainly.** Imported `notes/` payloads are
  operator-attached prose — redaction covers known patterns, not
  arbitrary secrets. Export files are only as safe as your ticket
  system. Screenshot bytes sent with consent are retained per the
  receiving provider's policy, not ours.
