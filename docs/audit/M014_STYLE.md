# M014 Art Direction — Cinematic Industrial Technology

## Direction

FieldRook is a precision diagnostic instrument used by professional
technicians. The M014 environment should feel like the dim control
room that instrument lives in: dark machined architecture, warm
distant equipment glow, delicate cyan instrumentation — calm,
substantial, intelligible. Atmosphere frames the interface; it
never competes with text.

Baseline references (M013, uncommitted): `.fieldrook-tmp/m14base/`.

## Environment composition

One wide raster environment (original, generated for this project)
plus the existing procedural layers:

- **Distant layer (raster):** dark abstract technological space —
  layered metallic masses, warm amber glow low-left (forge key),
  faint cyan accents high-right (instrument fill), deep shadow in
  the center where the reading column sits. Soft, low-frequency,
  no text, no characters, no literal room detail.
- **Middle layer (procedural SVG, kept from M013):** technical
  gridwork, circuit traces, pulsing nodes, raven watermark
  silhouette — the "instrument glass" between world and UI.
- **Near layer (CSS):** vignette + reading-well shadow that keeps
  contrast high behind content at every viewport.

Light logic is fixed: warm key low-left, cool fill high-right,
content in a shadow well. All views share this logic; per-view
tints shift its balance, never its direction.

## Materials

- **Structural** (header, context bar): dark titanium — near-flat
  with a brushed vertical gradient and a hard top-light edge.
- **Primary panels** (result header, landing card): elevated —
  directional highlight from the warm key, soft reflection band,
  deep drop shadow.
- **Secondary panels** (progress, timeline, rows): quiet — flat,
  low elevation, optimized for reading.
- **Floating** (evidence peek, dialogs): sharp elevation — strong
  keyline + large soft shadow, unambiguous separation.
- Glass/translucency is reserved for small instrument surfaces
  (centerpiece lens, badges), never large text areas.

## Color and contrast

Base: graphite `#0b0e12`, titanium `#131922`, gunmetal edges.
Gold `#e2a63d`: primary actions + warm key light only. Cyan
`#6fc3e8`: instrumentation, selection, links. Green: verified
outcomes only. Red: errors. Amber: uncertainty. Text always sits
on opaque surfaces or the shadow well — atmosphere may touch a
panel edge, never a paragraph.

## Motion principles

One coordinated slow system, all transform/opacity:

- Environmental breath: 60–120s light drift, barely perceptible.
- Instrument pulses: 4–8s node/sweep cycles.
- UI transitions: 200–400ms ease-out; entrances rise 8–10px.
- Pointer parallax: ≤6px on background layers only, rAF-driven,
  fine-pointer only, never on the reading surface.
- Static-first: every screen must look excellent frozen.

`prefers-reduced-motion` freezes everything (embers hidden,
parallax off, transitions instant) with zero capability loss.

## Visual hierarchy

Verdict → primary action → supporting evidence → metadata →
atmosphere. Scale, elevation, and light — not color count —
separate the levels. One primary action per screen (M012 rule kept).

## Brand-symbol placement

Three raven touchpoints, no more: the header RavenMark (only
persistent mark), the watermark silhouette in the environment,
one brief accent that travels the tab indicator when switching
major sections (short, subtle, non-blocking, reduced-motion off).
No mascots, no per-card birds, no fly-across animations.

## Landing composition

Identity (mark + wordmark) → investigation input (primary,
immediately usable) → new centerpiece (SignalScope instrument,
right column) → environment (frames, low-left warmth) → one
Investigate action. No splash, no intro gate, no delay.
