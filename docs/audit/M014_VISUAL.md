# M014 Visual Audit — Cinematic Atmosphere

Baseline: M013 `c92ba2e` + offline fix `49aada3`. All visual tests ran
with `FIELDROOK_OFFLINE=1` on isolated ports/DB; `/api/status` verified
`model_mode: simulated` before every capture run. Zero live Meta calls.

## Pass A — Creative baseline (M013 review)

Screenshots: `.fieldrook-tmp/m14base/` (not committed).

1. Background is abstract gradients + grid — atmosphere, not a place.
2. Light is uniform; no directional sources or warm/cool interplay.
3. Landing centerpiece is small and spinner-adjacent; hero is form-only.
4. One shared panel material; no structural/primary/secondary split.
5. Motion is decorative (embers, spins), not environmental.
6. Raven present but flat; no signature moment.
7. All views share identical atmosphere; no contextual light.
8. Secondary/mobile views correct but plain.

Style direction locked in `M014_STYLE.md`: cinematic industrial
technology — dark titanium, warm key low-left, cyan fill high-right,
reading well, three raven touchpoints max.

## Pass B — Art and composition

- `forge-hall.jpg` (1920×1280, 117KB production; source kept):
  original generated environment plate — metallic masses on the
  flanks, amber glow low-left, cyan accents high-right, near-black
  center. Provenance in `frontend/src/assets/env/README.md`.
- Layered integration: hall (parallax) → shade (reading well +
  vignette) → M013 grid/circuits/watermark → light → per-view tint
  → embers. M013 gradients remain as the no-image fallback.
- `SignalScope.tsx`: glass scope instrument (grid, waveform, sweep,
  corners, ticks, lamp) with honest `active` state; replaces
  InvestigationCore (deleted with its CSS).
- Material system: brushed titanium header/context, elevated
  hero/result panels with key-side sheen, quiet secondary cards.
- Per-view ambient tints via `data-view` (findings neutral,
  evidence cool, resolve warm, library faint slate).
- Tab-switch accent: the active indicator sweeps in once per change
  (verified mid-flight via slow-motion probe: scaleX 0.25 @ 1s/6s).
- Pointer parallax ≤8px on the hall only (rAF, fine-pointer,
  ≥700px, reduced-motion off). Verified via CSS var readback.

## Pass C — Interaction, motion, responsive

- 390/1024/1440/1920: no overflow (`scrollWidth` == viewport).
- Performance (headed Chromium, this workstation): ambient 75.2
  avg FPS (p50 13.3ms, p95 13.5ms); view-switch to painted 65ms;
  hall image 114KB / 7ms local. Headless rAF (~11fps) is a harness
  artifact, not app performance — documented, not claimed.
- Recording: `fieldrook-m014-tour.webm` (24.8s, 1280×720, 825KB).

## Pass D — Quality audit (10 items)

1. Hero scope said STANDBY while investigating → follows `busy`
   state with standby/active caption. Fixed.
2. Footer still read "Milestone 013" → 014. Fixed.
3. Evidence/resolve tints imperceptible at 7% → 9% alpha. Fixed.
4. Sparse pages (knowledge) crushed to black at the bottom →
   shade gradient softened (.8→.62). Fixed.
5. Standby sweep at 9s felt busy → 14s. Fixed.
6. Panel sheen direction contradicted the low-left key → `to top
   right` corner syntax. Fixed.
7. Waveform tail overshot the scope panel at sway extremes →
   clipPath to the glass. Fixed.
8. Core-stage vertical stretch attempt → looked worse (tall empty
   panel); reverted, compact stage kept. Reviewed.
9. Peek scroll stability re-verified: delta 0. Verified.
10. Reduced-motion re-verified programmatically: embers hidden,
    hall/wave/sweep `animation: none`, hall transform none, tint
    transition none, parallax never attaches. Verified.

## Pass E — M013 vs M014

Matched 1440px pairs: landing, findings, evidence, resolve, plus
mobile and 1920. M013 reads as gradients-behind-panels with a
circular core; M014 reads as an instrument inside a dim control
environment with architectural depth, directional light, and a
scope instrument. IA, workflows, and safeguards unchanged.

## Quality gate

- `pnpm run build` (tsc --noEmit + vite): clean, art hashed.
- Backend pytest: 263 passed (2:17; isolated temp dir for the
  known WinError-5 teardown quirk).
- Playwright E2E: 21/21 (1.6m, `FIELDROOK_OFFLINE=1` stack).
- Gauntlet offline: 37/37, exit 0.
- Keyboard: M013 tab order/focus/labels preserved.
- Console/page errors across all runs: none.
- Secret scan: gitleaks binary absent (known limitation, not in
  CI either); pattern scan over new/changed files clean; root
  `.env` never read; every test backend ran `FIELDROOK_OFFLINE=1`.

## Definition of done

Substantially more atmospheric than M013 ✓ · coherent identity ✓
original artwork integrated ✓ · alive but calm ✓ · crafted
surfaces ✓ · convincing depth ✓ · restrained raven ✓ · no
fantasy/game read ✓ · functionality intact ✓ · tests green ✓ ·
acceptable performance (measured) ✓ · real recording ✓ · clear
before/after ✓.

Known limitations: backdrop blur stays confined to the sticky
views bar; parallax is fine-pointer-only by design; the tour is
VP9 825KB; HACKATHON.md's commit table remains on its
release-time docs cadence (stale since M005, matching precedent).
