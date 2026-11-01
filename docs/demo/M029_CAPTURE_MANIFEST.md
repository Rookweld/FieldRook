# M029 — Native capture manifest (P3)

Source build: frozen M029 desktop + shell from worktree `m029/prove-polish-record`
(`C:\tmp\m29-wt-fix`), built to `C:\Users\pontu\.fieldrook-tmp\m29-dist\`.
Recorded: 2026-11-01 ~00:56–01:28 UTC. App: PID 50464, isolated port :8131,
isolated data `C:\Users\pontu\.fieldrook-tmp\m29-capture\data`,
`FIELDROOK_FIXTURE_WORKER=failing`. Model: `fieldrook-simulated-001`
(SIMULATED, badged in every shot). Operator :8000 / data untouched.

## Cases recorded (fixture data only)

- `inv-8fb657bec4c9` — "The FieldRook demo worker is down and will not come
  back up." 5 evidence records, 1 proposal (`prop-75001ba0464b`
  `recover_demo_worker → demo-worker`), 1 execution (`exe-a923fa54f26f`
  VERIFIED_RESOLVED), 1 resolution plan (`plan-845d775c0496`, manual claim →
  Confirm Fix → NOT_RESOLVED, verification `ver-281bedb9`, 1/2 criteria pass).
- `inv-c7c4c6460ccc` — "DNS does not resolve anything since this morning."
  3 evidence records (`get_dns_config` ev-1 + ev-3 re-check pair,
  `test_dns_resolution` ev-2). Network Lab re-check → "Fresh reading recorded
  as ev-3 (unchanged)." (P1 success-notice fix visible on camera.)

## Deliberate fault injection (disclosed, fixture-scoped)

After the registered recovery genuinely verified (`after_state` healthy,
verified worker PID 47176), the operator killed the owned fixture process
`fieldrook-demo-worker` (PID 47176) to stage the failed-verification beat.
The subsequent baseline (`ev-4`, status `failed`), manual claim, Confirm Fix
re-measurement (`ev-5`), and NOT_RESOLVED grading are all real app behavior
against the re-broken fixture. The narration states this openly.

## Files (SHA-256)

Raw session: `C:\Users\pontu\.fieldrook-tmp\m29-capture\raw\m29-raw-session.mp4`
(1580x880 h264, 1864.93 s, 27,604,312 bytes)

- `c39d3cfdfcce67f2b7540596b06206c5d26c671ede880eed6924e435a5d4e89a`
  27604312 m29-raw-session.mp4

Exported report: `C:\Users\pontu\.fieldrook-tmp\m29-capture\artifacts\inv-8fb657bec4c9.md`
(real in-app Download Markdown, secret-scanned clean)

- `fa6c9f679c363435a7ce0412a8b0dc73104a500a8c3ad8cd789af534b1ca8e20`
  11281 inv-8fb657bec4c9.md

Stills: `C:\Users\pontu\.fieldrook-tmp\m29-capture\stills\` (OS-level pixels,
CDP input only; shot16/shot16b identical — Escape did not dismiss the
Edge downloads popup; it was closed via DevTools `/json/close/` instead):

- `51226feddfcc9f63b4f340dc720a7a33766005e6da949165674adecef18b3644` 481684 shot01-launchpad.png — Launchpad hero (pre-record)
- `c483b7f24d1c4ac0c91fc7afed8e69c990a51e1bdc2643810d4204cf0e005ecf` 387462 shot02-intake.png — intake hero, empty
- `72634eaac459631b3df271a4b076925607cc26a654ffdf8ec5e9398b0edf4e06` 242518 shot02-intake-filled.png — filled form (take 1)
- `0fc0811f4da2f9694b811bf010ea1bfe8efd82e567abe7585903b18537b7d7ed` 222206 shot03-investigating.png — Findings, ev-1 worker failed
- `38c2cd9198638ee5fb5363512e477923fac8ac46c326a85383ae2f748417a8ce` 237635 shot04-resolve-proposal.png — Resolve tab context
- `66295578b4ce0f23d58ab061852b6a5edf60acdb2b0f450aad7ab0eafb981e3b` 216131 shot05-proposal-approve.png — AWAITING_APPROVAL + Approve
- `19f3e1b4f62224321bd16edee6cf5d3901c13aaf7d3a2db9bdb4957640b78865` 217239 shot06-approved-execute.png — approved, nothing executed yet
- `20d353d066ddbbed924fb6744eec64124384a8ee1f32485a34777b67753bc712` 212900 shot07-verifying.png — Executing…
- `7fe0fded247e81f9024444388e8df490cffc4e4060175da2617f57fdce506311` 214692 shot08-verified-resolved.png — VERIFIED_RESOLVED, before→after
- `c985f55c6e6934f91672d1975d1e3ced515587585b4c11129a3b0b73db6bf5aa` 215628 shot09-resolution-plan-form.png — plan template form
- `8ca6ad6b4f24ed88173c69b14b5d69f266bfd948a1265186e3365435732cff9a` 219083 shot10-plan-ready.png — 2 templated criteria
- `f5606d74a61a00518534d568be5a2dcc12b63a41e3efd908a6897732c1429497` 227606 shot11-plan-created.png — plan queue state
- `9409a695ffc393076061ed6feb8a5550749b747ddc977ac42382c94c9f65cd94` 218739 shot12-record-manual.png — claim input + baseline pair
- `3665558d51b5145b15674637268dfa04b30f3bec9a489ee7f938a93dad63e266` 219410 shot13-claimed-confirm.png — claim recorded, Confirm Fix
- `6bfd26f5b645e1c4de2b8022a2e3b13c6b4f7d743c3eb63703bf6bc19df3e6d3` 215199 shot14-not-resolved.png — NOT_RESOLVED 1/2, money shot
- `8d7b4c5450c136d593bd5135b500a55446d15fda4108cccea865133478c83717` 238338 shot15-evidence-timeline.png — action pair + ev-4→ev-5
- `47f87f2a31b56cd385e32371c6fc39d7291e4481302e0d5732489ff74907a18e` 254350 shot16-netlab.png — Lab + downloads popup (dup of 16b)
- `47f87f2a31b56cd385e32371c6fc39d7291e4481302e0d5732489ff74907a18e` 254350 shot16b-netlab-clean.png — (same bytes as shot16)
- `fd17f928628c61937a0e8f4835d79266ffe21226f525b2984a700e5b72b31a1f` 254368 shot16c-netlab-clean.png — popup persisted after OS click miss
- `7a51ec4d869d0b560b4d8417d9d6506d962070b399e67f37867feda80e5e6a94` 261693 shot16d-netlab-clean.png — clean Lab after target close
- `8934ea57322e2c06be3cf455108d14893b631d471a97db01c2f2f9c35c22a3a2` 196500 shot17-netlab-recheck-ready.png — consented re-check armed
- `ee90ad11718f2c8bb0e96c14e1156db48fbad5b77191ae84578bf5c839312fe3` 194522 shot18-netlab-success.png — ev-3 re-check landed
- `45c875a51301f746d4ffc2eedb9d2df11757a8ac835a1bd985e71f97afd766f0` 202771 shot18b-netlab-notice.png — success notice framed (P1 fix)

## Provenance notes

- All footage is the real frozen native app on Windows; no mockups, no
  AI-generated UI, no live-cloud data. Fixture readings labeled FIXTURES /
  SIMULATED in-app.
- CDP drove input only (clicks, typing, scroll); all pixels are OS-level
  screen capture (ffmpeg gdigrab + screenshot skill).
- Live Meta proof: NONE (MODEL_API_KEY absent, boolean-checked). Voiceover
  "the model" always means the simulated provider; see
  `docs/demo/M029_META_PROOF_STATUS.md`.
