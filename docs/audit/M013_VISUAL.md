# M013 Visual Audit

## Pass A — M012 baseline weaknesses (2026-10-27)

Screenshots: `.fieldrook-tmp/m13base/` (not committed).

1. **Flat uniform background.** `var(--bg)` covers every pixel; header,
   tabs, cards, and page share near-identical charcoal with no
   environmental identity.
2. **Zero elevation hierarchy.** Cards, context bar, buttons, and the
   peek overlay are all flat rectangles with 1px borders; nothing
   floats, nothing recedes.
3. **Buttons are paint, not objects.** Gold fill with no depth,
   specular response, or pressed physics; ghost buttons are bare
   outlines.
4. **Static.** The only motion in the product is the pending dot pulse
   and CSS hover color shifts. Tab switches, peek open/close, and
   result arrival are instant cuts.
5. **Forgettable landing.** Competent form, zero identity — no mark,
   no focal point, nothing a technician would remember.
6. **Result header underplays the verdict.** Status pill and finding
   share the same card weight as every other section below them.
7. **Evidence reads as containers, not instruments.** Summary rows are
   legible but visually generic; group heads are plain uppercase text.
8. **No brand presence beyond the ♜ glyph.** ROOKWELD's forge/raven
   identity appears nowhere in the interface.

## Pass B — Visual reconstruction (2026-10-27)

New additive layer in `frontend/src/App.css` (~700 lines, M012 rules
untouched) plus three small components. No API, backend, hook, or
navigation changes.

- `Atmosphere.tsx` — fixed environmental backdrop: layered
  forge-gold/cyan gradients, procedural SVG gridwork with circuit
  traces and pulsing nodes, watermark raven silhouette (original
  polygons), 8 rising embers. `pointer-events: none`, `aria-hidden`.
- `InvestigationCore.tsx` — original raven-instrument SVG: counter-
  rotating cyan/gold rings, sweep arc, pulsing gold heart. Claims no
  diagnostic stage; the pending panel keeps its honest elapsed timer.
- `RavenMark.tsx` — original geometric raven for the header brand.
- Elevation system: environment → structural surfaces → content
  panels → controls → floating popovers, via layered gradients,
  inset top-light, 1px near-black keylines, and `--shadow-1..4`.
- Tactile buttons: gold gradient + specular inset + hover lift +
  pressed inset; quieter ghost/danger variants; no layout shift.
- Motion: 90s grid drift, 14s light breathing, ember rise, core
  float/spin/pulse, view/peek/result entrance transitions — all
  transforms/opacity, all frozen under `prefers-reduced-motion`.
- Landing hero: copy + core grid with the Diagnostic Core
  centerpiece in a scanlined instrument stage.

**Pass B defect (found by screenshot, fixed before Pass C):** the
fixed `.atmosphere` (positioned, z-index 0) painted ABOVE the
non-positioned header/nav/main and hid all content — diagnosed by
removing the layer (content reappeared) and fixed with
`.app > :not(.atmosphere) { position: relative; z-index: 1; }`.

Screenshots (1440×900, simulated model + fixtures): landing,
pending, findings, evidence, evidence peek, resolve, history,
knowledge, 390px mobile landing/findings. Zero console/page errors.

## Pass C — Art-direction refinement (2026-10-27)

Eight concrete fixes from rendered-screenshot review:

1. **Mobile horizontal overflow (critical).** The hero grid's `1fr`
   track expanded to the longest service-select option's min-content
   (53 chars, "Background Intelligent Transfer Service (BITS) —
   Stopped"), pushing `scrollWidth` to 481px on a 390px viewport.
   Fixed with `minmax(0, 1fr)` tracks, `min-width: 0` on hero copy
   and the controls field, `max-width: 100%` on inputs, wrapping
   file row. Verified: `scrollWidth` 481 → 390.
2. **Pending core read as a dim blob** at 56px — added a cyan
   drop-shadow glow so the in-flight instrument reads as active.
3. **Mobile centerpiece oversized** — core scales to 104px under
   900px width.
4. **Raven watermark nearly invisible** — fill `#141c27`→`#1b2534`,
   opacity 0.55→0.6. Present but still restrained.
5. **Cards lacked directional light** — 1px lighter top edge
   (`#2e3947`) for a machined top-light read.
6. **History rows gave no hover feedback** — border-color transition
   + hover lift of the edge tone.
7. **Native scrollbars clashed** — restrained dark thin scrollbars
   (webkit + Firefox `scrollbar-color`).
8. **Disabled gold button text muddy** — `#8a8172`→`#97907e`, still
   clearly disabled.

Non-issues confirmed by probe: the 390px tab strip is M012's
intentional horizontal scroller (`nowrap` + `overflow-x: auto`);
the evidence peek already floats with margin, radius, and shadow.

## Pass D — Final review (2026-10-27)

- 1920×1080, 1440×900, 1024×768: no overflow, atmosphere scales,
  content capped at 1060px and centered.
- 390×844: landing and findings fit exactly (`scrollWidth` 390).
- Reduced motion (`reducedMotion: reduce`): embers `display: none`,
  grid/ring/core `animation: none`, media query matches — verified
  programmatically, not just by screenshot.
- Keyboard: logical tab order (tabs → presets → textarea →
  select → file → fixtures), 2px gold focus outlines (gold halo
  ring on text inputs), h1×1/h2×1, all textareas labeled, no
  imageless-alt gaps. Escape dismisses the peek (E2E-covered).
- Recording: `docs/assets/fieldrook-m013-tour.webm` (21s, 1280×720,
  landing → investigation animation → findings → evidence → peek →
  resolve → history).
- Real workflows A–F pass via the E2E suite (21/21): phantom-task
  suspicion (A), crash runbook (B), honest UNRESOLVED (C),
  peek without page jump (D), approve/execute/verify (E), knowledge
  match + search/delete (F).

## Quality gate (2026-10-27)

- `pnpm run build` (tsc --noEmit + vite): clean.
- Backend pytest: 252 passed (2:39). Note: the stock `%TEMP%`
  pytest symlink teardown hits WinError 5 on this machine; reran
  with an isolated temp dir — environment quirk, zero test impact.
- Playwright E2E: 21/21 passed (1.6m), isolated 8123/4173 stack.
- Diagnostic gauntlet (offline): 37/37, exit 0.
- Secret scan: gitleaks binary absent on this machine and not in
  CI (known environment limitation, same as M007); manual pattern
  scan over every M013-touched file clean; root `.env` stays
  gitignored and unread.
- Console/page errors across all capture runs: none.

## Incident — accidental live-model call (2026-10-27)

During final captures the audit backend was relaunched with
`$env:MODEL_API_KEY=''` intending simulated mode. PowerShell does
not propagate empty-string variables to child environments, so the
key was absent and `app/config.py`'s root-`.env` fallback loaded
the operator's real key. Exactly ONE live-model investigation ran
(synthetic problem text + fixture diagnostics — no operator or
system data; written to the isolated audit `m13.db`, never the
operator's store). The backend was stopped immediately on
discovery. Verified simulated (`/api/status` → `model_mode:
simulated`) before every later capture by passing a whitespace key
(non-empty, survives inheritance, strips to empty).

Recommendation: add an explicit `FIELDROOK_OFFLINE=1` (or
`--no-live`) backend flag so test stacks never depend on env
tricks to stay offline. The four screenshots from the live-backed
run were discarded from the deliverable set.

## Definition of done

1. Landing has an unmistakable centerpiece (Diagnostic Core). ✓
2. Convincing atmosphere and depth (grid/circuits/raven/embers). ✓
3. Tactile responsive buttons. ✓
4. Deliberate elevation hierarchy. ✓
5. Motion makes the product feel alive. ✓
6. Professionally art-directed, visibly beyond M012. ✓
7. Background never interferes with reading (opaque surfaces). ✓
8. Diagnose/resolve workflows intact (E2E 21/21). ✓
9. Tests and security boundaries survive (252 + 37 + scans). ✓
10. Screenshots + recording demonstrate the transformation. ✓

Known limitations: backdrop blur is confined to the sticky views
bar (full-app blur avoided for GPU cost); the tour video is 3.4MB;
HACKATHON.md's commit table was already stale after M005 and is
left for the release-time docs pass, matching M006–M012 precedent.
