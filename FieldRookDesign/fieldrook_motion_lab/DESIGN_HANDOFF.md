# FieldRook Motion Lab — Visual Direction / Study 03

**Status:** Interactive visual prototype, not FieldRook source code. No live diagnostic, filesystem processing, backend, API requests, or AI inference. No external runtime or network resources.

## Intent

A retro-futuristic *technician's instrument*, not a generic SaaS dashboard. Warm plum/aubergine surfaces, radiant coral, acid-lime interaction accents, bold editorial typography, signal apparatus and fine illuminated circuit paths.

## Try it

Open `index.html` in a desktop browser. It is self-contained and works offline.

- Switch **Alive / Quiet / Off** to compare motion intensities.
- Switch **Launchpad / Workbench / Evidence / Knowledge / Settings**.
- Click **Start Guided Check** to advance a **clearly simulated** diagnostic step.
- Add a note to see the inspector and evidence list update; data disappears when you reload.
- Click **Import Collector package** to choose a `.zip` file; *only the file name is shown*, no bytes are processed or uploaded.
- Click **New Investigation** to create a fictional in-memory case.

## Motion system

| Element | Motion | Purpose | Budget |
| --- | --- | --- | --- |
| Circuit background | Slow SVG stroke-dashoffset + glowing nodes | Low-priority atmosphere; strongest outside work area | 13–18 s loops |
| Signal trace | Traveling line segment on ECG-like SVG | Activity cue, **not telemetry** | 4.8 s loop |
| Sunrise orbit | Single hairline rotation | Soft instrument identity | 20–70 s |
| Rook shape | Gentle vertical drift | An editorial signature, can be removed if distracting | 9 s |
| Buttons and cards | Small hover elevation | Affordance | 150–200 ms |

Quiet mode lengthens and dims movement; Off mode disables animation. `prefers-reduced-motion` defaults to Off. A future implementation must wire activity-state motion to **actual product state** and pause/dampen ambient effects during sustained troubleshooting.

## What the design does not assert

- No real issue diagnosis, computer measurements or Collector import.
- No live health percentage (the dial shows **illustrative workflow steps**, not confidence).
- No real desktop titlebar, native dialogs, installation or process lifecycle.
- No persistence, real provider connection, cloud permission, or collector execution.

## Integration guidance for Muse, later

- Keep M025/M026 evidence security and target isolation as the source of truth.
- Use design tokens rather than hardcoding colors across individual components.
- Build a real Windows shell with proper application lifecycle separately from this HTML proof of concept.
- Implement animations using CSS/SVG with composited transforms and bounded paints; profile CPU/GPU at laptop resolutions.
- Respect reduced motion and keyboard access; avoid animated décor behind long-form reading.
- Replace fictional workbench values with typed product state. Never label model-generated assumptions as measured facts.
- Audit WCAG contrast and 1366×768 layout before release. Treat image-derived visual effects as references, not source assets.
- Do not paste this single HTML wholesale over the real React UI. Extract components, design tokens and motion primitives incrementally.
