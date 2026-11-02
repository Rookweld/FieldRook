# M029 — Narration lock draft + shot-to-voice sync (P4)

Voice: **Pontus English Natural V4**, Suno voice ID
`5e89651b-01ab-442d-b26f-8cb2928bb422` (see
(narrator lock note, kept out of the repo). Style: natural spoken English
documentary narration; warm, grounded, unhurried; clear "FieldRook"; no
singing, no music, `backing_music=false`. Reference pace: winning V4-B take
≈ 40 words / 17.6 s (≈136 wpm + pauses).

Script: **298 spoken words in 7 chunks** (6–8 required). Rough cut:
**176 s, silent**, assembled ONLY from verified raw offsets below
(raw: `<fieldrook-tmp>\m29-capture\raw\m29-raw-session.mp4`,
1864.93 s; every segment below was spot-checked on real frames).
Deliberate pauses sit around tool proofs and the NOT_RESOLVED hold.
All on-screen analysis is SIMULATED (`fieldrook-simulated-001`, badged);
no live Meta inference is claimed anywhere (see M029_META_PROOF_STATUS.md).

## Narration chunks (exact take text)

### C1 — Hook · rough 0:00–0:12 (scenes 1–2) · 35 words
> When a Windows computer breaks, a technician gets a symptom, not an
> explanation. Logs, services, and network state live in different tools;
> FieldRook brings them together. I built it to replace guessing with
> measured evidence.

### C2 — One case · rough 0:12–0:40 (scenes 3–4) · 51 words
> I start with a user report: the demo worker is down. FieldRook opens a
> case, pins it to this computer, and investigates through registered
> diagnostics only. The simulated model can request one tool here:
> get_demo_worker_health. It cannot invent shell commands. Everything you
> see runs on labeled fixture data.

### C3 — Evidence, proposal, human gate · rough 0:40–1:06 (scenes 5–6) · 38 words
> The reading lands as timestamped evidence: worker failed. Facts,
> hypotheses, and open questions stay separate. The model proposes exactly
> one registered recovery — and waits. Nothing runs until a human approves.
> Approval is single-use and expires in minutes.

### C4 — Execute, verify by measurement · rough 1:06–1:28 (scenes 7–8) · 41 words
> I approve, then execute as a separate step. FieldRook re-reads the worker
> through the same registered tool and grades the outcome from fresh
> evidence — verified resolved, before unknown, after healthy. That is the
> whole product idea: proof from measurement, not claims.

### C5 — The harder test (disclosed fault injection) · rough 1:28–1:50 (scenes 9–10) · 37 words
> Now the harder test. We stop the worker again — openly, to prove the
> refusal path. I draft a plan with measurable criteria, record a manual
> fix as a claim only, and ask FieldRook to confirm it.

### C6 — Honest verdict · rough 1:50–2:18 (scenes 11–12) · 49 words
> Re-measurement disagrees: still failed, one of two criteria pass. The
> honest verdict is NOT resolved — a claimed fix that measurement
> disproves, caught on the record. Every reading stays in the timeline;
> re-checks add, never rewrite. The ticket-ready report carries it all:
> evidence, approvals, and the verified outcome.

### C7 — Network Lab + close · rough 2:18–2:56 (scenes 13–16) · 47 words
> A second case shows the Network Lab: consented, read-only re-checks of
> real DNS readings, each with its tool and source. All analysis here is
> simulated and labeled; live Meta tool calls stay a separate, explicit
> step. Local engine, typed tool registry, audit trails. FieldRook. Less
> guessing. More evidence.

## Shot-to-voice sync sheet (rough-cut timeline)

| # | Rough time | Raw source | Picture | Voice |
|---|-----------|------------|---------|-------|
| 1 | 0:00–0:04 | still shot01-launchpad.png ×4 s | Launchpad hero | C1 starts |
| 2 | 0:04–0:12 | raw 66–74 | NAME THE SYMPTOM hero | C1 |
| 3 | 0:12–0:26 | raw 168–182 | Filled intake + Investigate | C2 |
| 4 | 0:26–0:40 | raw 187–201 | Findings: ev-1 worker failed | C2 |
| 5 | 0:40–0:50 | raw 302–312 | Resolve: proposal card | C3 |
| 6 | 0:50–1:06 | raw 334–350 | AWAITING_APPROVAL → Approve | C3 |
| 7 | 1:06–1:20 | raw 430–444 | Execute → Executing… | C4 |
| 8 | 1:20–1:28 | raw 507–515 | VERIFIED_RESOLVED before→after | C4 (pause on frame) |
| 9 | 1:28–1:36 | raw 624–632 | Templated criteria | C5 |
| 10 | 1:36–1:50 | raw 880–894 | Manual claim → Confirm Fix | C5 |
| 11 | 1:50–2:10 | raw 952–972 | NOT_RESOLVED 1/2, ev-4→ev-5 | C6 (long hold) |
| 12 | 2:10–2:18 | raw 1000–1008 | Evidence timeline, re-checks | C6 |
| 13 | 2:18–2:24 | raw 1380–1386 | Network Lab hero | C7 |
| 14 | 2:24–2:44 | raw 1736–1756 | Consent → re-check → ev-3 | C7 (pause on SIMULATED line) |
| 15 | 2:44–2:52 | raw 1803–1811 | "Fresh reading recorded as ev-3" | C7 |
| 16 | 2:52–2:56 | still shot18b-netlab-notice.png ×4 s | Notice end hold | C7 tagline |

Total: 176 s. Edit script: `<fieldrook-tmp>\m29-capture\Build-RoughCut.ps1`
→ `<fieldrook-tmp>\m29-capture\rough\m29-roughcut-silent.mp4`.

## Suno take instructions (per chunk C1–C7)

- One `speech_create` call per chunk with the exact text above; same voice
  ID, `backing_music=false`, documentary style from the voice lock.
- Audition each take; cherry-pick for tone match to V4-B reference
  (stochastic TTS — takes will vary). Keep DRY stems, no music bed.
- Pronunciation: "FieldRook" (two beats), "NOT resolved" (spelled verdict,
  slight pause before), "get_demo_worker_health" (read as "get demo worker
  health"), "ev-4 to ev-5" (only if ad-libbed — not in script).
- Target per-chunk durations: C1 ≤12 s, C2 ≤26 s, C3 ≤24 s, C4 ≤20 s,
  C5 ≤20 s, C6 ≤26 s, C7 ≤34 s. If a take runs long, trim pauses first,
  never speed up the voice.

## Still needed for the final ≤180 s mix (needs manifest)

1. Dry V4 narration stems C1–C7 (Suno, owner-operated: voice ID is
   creator-owned/private; assistant must NOT generate without instruction).
2. Original legal instrumental underscore stem (separate; duck under voice).
3. Captions: burn in SIMULATED MODEL + FIXTURE DATA labels on scenes 4–12
   (already badged in-app; captions reinforce), NOT_RESOLVED emphasis card.
4. Optional 15–25 s live-Meta insert: ONLY if a genuine keyed run is later
   captured; re-record scene 14 region only, keep SIMULATED elsewhere.
5. Final loudness/pass: MP4 ≤180 s, 1080p check, no secrets, hashes logged.
