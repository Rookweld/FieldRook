# M026 Discord showcase draft (DO NOT POST without explicit authorization)

Prepared for the hackathon Discord. Check the actual posting rules and
eligibility before any submission-related claim. All statements below are
verified against the M026 validation record (docs/M026_DELIVERY.md); do
not embellish beyond it.

---

## 1. Main announcement (post as-is, English)

**FieldRook M026: a native Windows diagnostic workstation with a living interface**

FieldRook is an evidence-driven Windows troubleshooting assistant: it
collects read-only diagnostics (local tools or a portable Collector
package from the affected machine), keeps every claim cited to evidence
it actually measured, and refuses to guess when measurements are
missing. Diagnose. Verify. Resolve.

M026 rebuilds it as a real native Windows app:

- **Native shell**: WPF + WebView2 host, own window, taskbar presence,
  native file dialogs, drag-and-drop Collector import, single-instance,
  fenced shutdown that reaps only its own backend. No browser tab, no
  orphan processes, no Python/Node install needed (self-contained).
- **SIGNALFORGE visual system**: a retro-futuristic instrument look
  (deep plum, coral, acid-lime) rebuilt from the approved Motion Lab
  prototype — launchpad, technician workbench, evidence inspector,
  knowledge library, settings.
- **Motion system**: subtle circuit-vein ambience, an ornamental signal
  trace (honestly labeled — never presented as telemetry), Alive/Quiet/
  Off profiles, reduced-motion respected, ~1.2% idle CPU.
- **Same honest engine**: fixtures/simulated/live provider modes,
  approval-gated actions, Collector integrity validation, wrong-machine
  recheck protection, case export. 47/47 E2E, 684 backend tests, 66
  shell tests green.

Portable build: one zip, WebView2 Runtime the only prerequisite.
Repo + demo video: <links when published>.

ROOKWELD — FORGE. BUILD. IMAGINE.

## 2. Technical follow-up (reply in thread)

Architecture notes for builders:

- The .NET shell spawns the existing FastAPI backend as an **owned
  child process** (loopback-only, health-gated on a desktop-identity
  status field) and kills only what it spawned — PID-fenced, no
  grandchildren chasing. A named mutex gives single-instance; a second
  launch shows a dialog and exits 0.
- The JS↔native bridge is **typed and allowlisted** (open/save dialogs,
  version, window control) plus file-drop push. Unknown ops fail closed;
  traversal and non-loopback targets are rejected. 66 unit tests pin
  the shapes on both sides.
- The React UI keeps the proven diagnostic engine untouched underneath:
  the new views are prop-driven shells over real investigation state,
  with the engine mounted stably so creating a case never remounts it
  (that remount was a real release-blocker we caught in validation —
  fixed with a stable React key across the hero branch flip).
- Motion is CSS/SVG composited only — zero JS animation loops — with
  measured frame stability and a persisted Alive/Quiet/Off preference.
- Validation was independent: a separate validator agent ran the full
  gate (pytest, Playwright, gauntlet, frozen-app smoke, security
  probes, screenshots vs the design reference) and blocked the release
  until the Investigate→case loop was proven in the shipped bundle.

## 3. Screenshot/video posting order

1. `z2-g6-01-launchpad-cold.png` — native window frame + launchpad
   (the "it's a real app" shot).
2. `z2-g7-02-direct-adopted.png` — workbench with a live adopted case.
3. `z2-g7-03-evidence.png` — evidence inspector.
4. `z2-g7-05-imported.png` — Collector import result.
5. `z2-g7-06-resolution.png` — resolution/verification.
6. `z2-minor4-frame-height.png` or `z2-g6-02-maximized.png` — maximized.
7. Demo video (.webm journey capture) — post last, it threads the story.
8. Motion close-up: crop of the signal trace / circuit veins (GIF if
   converted; otherwise a still with a caption).

Full inventory with paths: docs/M026_DELIVERY.md § Screenshots.

## 4. One genuinely interesting dev insight

**Your E2E suite can go from 40 failures to 47/47 green with a one-line
React key.** Our redesign wrapped the diagnostic engine in a hero that
flipped layout branches when a case was created — moving the engine's
DOM position, which silently remounted it, wiped the intake, and
orphaned the server-side case. The suite caught it (35 timeout
failures); the validator root-caused it to reconciliation, not logic;
the fix was giving the engine's section the same stable key in both
branches so React moves the node instead of remounting. The lesson:
when a redesign composes old components into new layouts, test the
composition seam itself — state preservation across layout flips —
not just the views on either side.
