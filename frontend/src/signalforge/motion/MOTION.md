# signalforge/motion (M026 DELTA)

Working motion primitives extracted from `FieldRookDesign/fieldrook_motion_lab/`
(keyframes and budgets only). CSS/SVG with composited transforms
(`transform`/`opacity`) plus SVG `stroke-dashoffset` — **no JS animation
loops** anywhere in this folder.

## Files

| File | Purpose |
| --- | --- |
| `motion.css` | All keyframes, mode switches, quiet/off, work-damp, reading guard, reduced-motion + forced-colors + narrow-viewport rules |
| `motionPreference.ts` | `fieldrook.motion.v1` persistence, `body[data-motion]` init, `useMotionMode`, `setWorkHeavy` |
| `MotionSwitcher.tsx` | Keyboard-operable Alive/Quiet/Off radiogroup |
| `CircuitVeins.tsx` | Atmospheric circuit pulses (13s/18s) |
| `SignalTrace.tsx` | ECG travel (4.8s) + bounded activity sweep |
| `InstrumentOrbit.tsx` | Hairline rings (20–70s) |
| `index.ts` | Barrel export |

`main.tsx` (narrow wiring edit) imports `motion.css` and calls
`initMotionPreference()` before first paint.

## Preference: `fieldrook.motion.v1`

Values `alive|quiet|off`, persisted in `localStorage`, applied as
`body[data-motion]`. Resolution: stored value wins; else
`prefers-reduced-motion` defaults to `off`; else `alive`.

**Prototype mapping:** the Motion Lab used `ambient|quiet|off` for
`body[data-motion]`. The product renames `ambient` → `alive`
(`parseMotionMode` maps legacy stored `ambient` to `alive`).

## Budgets (from DESIGN_HANDOFF.md)

- Circuit pulses: 13s / 18s dashoffset loops, nodes 5.5s (opacity+scale only —
  the prototype animated SVG `r`, a geometry repaint; DELTA uses transform).
- Signal trace: 4.8s travel loop; activity sweep is a single 1.2s run.
- Orbits: 70s ring / 20s scan, clamped to 20–70s; quiet lengthens to 120s/65s.
- Feedback: hover elevation 150–200ms (`.sf-pressable`, 180ms), toast 230ms.

## SignalTrace activity subscription

`activityPulse?: number` — a monotonic counter the parent bumps on **real app
activity only**: navigation, panel expand/collapse, action confirm. Each new
value plays one highlight sweep over the idle loop (CSS animation retriggered
by React `key`; still no JS loop). Never wire to timers, keystrokes, focus
follow, or polling. The trace is **ornament, never telemetry**: no labels, no
units, `aria-hidden`. Wrapping it with CPU/network/health/AI captions is a
contract violation (M026 §4).

## Placement rules

- `CircuitVeins`: hero/launchpad chrome only — **never behind reading
  panels**. Backstop: `.sf-reading .sf-motion-decor { display: none }`.
- Work-heavy views (sustained troubleshooting) call `setWorkHeavy(true)` on
  mount / `setWorkHeavy(false)` on unmount; `body[data-focus="work"]` fades
  circuits to 0.12, slows orbits, dims the trace, stills the activity dot.
- Decor is `pointer-events: none`, `overflow: clip`, never creates scrollbars.

## Accessibility

- `MotionSwitcher` uses native radios: tab + arrow keys, visible
  3px focus outline, 13px semibold labels, 40px targets (44px under 480px
  width), wraps without clipping.
- `forced-colors: active`: decor hidden, switcher uses Canvas/ButtonText/
  Highlight system colors.
- Decor is `aria-hidden`; components accept `ariaLabel` only when a host
  gives them meaning (default: hidden).

## Measured on real hardware

Host: 13th Gen Intel i7-13850HX (28 logical), Windows 11, Playwright
Chromium 1248 headless, 1280x720, full decor set (circuits + trace + orbit
+ dot), 6s true-idle windows (no JS running), process-tree CPU. Method:
`.fieldrook-tmp/delta-motion/measure.js` (forge tooling, not shipped).

| Mode | Idle CPU (% one core) | fps | mean/p95/max gap |
| --- | --- | --- | --- |
| alive (software raster) | 44.3 | 60.0 | 16.67 / 16.7 / 16.8 ms |
| quiet (software raster) | 50.4 | 59.9 | 16.67 / 16.7 / 16.8 ms |
| off (software raster) | 0.0 | 60.1 | 16.67 / 16.7 / 16.8 ms |
| blank control | 0.2 | 60.1 | 16.67 / 16.7 / 16.8 ms |
| alive (d3d11/gpu-raster flags) | 28.0 | 59.9 | 16.67 / 16.7 / 16.8 ms |
| quiet (d3d11/gpu-raster flags) | 27.8 | 60.0 | 16.67 / 16.7 / 16.8 ms |
| off (d3d11/gpu-raster flags) | 0.24 | 60.0 | 16.67 / 16.8 / 16.8 ms |

Verified via computed style: `off` reports `animation-name: none` on all
six animated targets (this check caught and fixed a scoping bug where
descendant animations survived `off`). Run-to-run variance ≈ ±6pp, so
alive≈quiet is noise, not signal — quiet dims/slows perception; only
`off` (or work-heavy damp) removes frame work. The 28–50% software-render
cost is SVG dashoffset repaint rasterized on CPU by headless SwiftShader
(a no-GPU worst case); the production WebView2 shell is GPU-backed, where
transform/opacity composite and repaints are GPU-rasterized. Frame
delivery is a locked 60fps with zero jank in every mode.

Responsive (alive mode, worst case): 1920x1080, 1280x720, 360x640 — no
horizontal overflow anywhere, switcher fully inside viewport; option
labels 40px tall at desktop, 44px full-width rows at 360px.

## Ownership

DELTA owns `signalforge/motion/**`, the `main.tsx` prefs wiring, and
signalforge CSS only. Palette hexes live ONLY in BETA's `tokens.css` —
`motion.css` references them via `var()` over system-color/currentColor
bases and declares zero hexes.
