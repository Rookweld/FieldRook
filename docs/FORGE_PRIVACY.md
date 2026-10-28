# FORGE privacy review (M024, evidence-based)

Scope: data flows introduced or touched by FORGE (collector, toolpacks,
knowledge/reference, investigation turns, workstation) plus the
pre-existing boundaries they rely on. Every claim below names the code
or test that enforces it. No live traffic was inspected; no real user
data was used.

## 1. Network boundaries

| Flow | Enforcement |
|---|---|
| API listens on loopback only | All start paths pass `--host 127.0.0.1` (`start-fieldrook.bat`, `docs/FIRST_RUN.md`, E2E `playwright.config.ts`) |
| Local model endpoint is loopback only | `validate_local_model_url` (`backend/app/analysis/provider.py`) rejects any non-loopback host before any request; covered by loopback security tests |
| Cloud calls require explicit selection | Provider selector (`auto`/`meta`/`simulated`/`local`); `FIELDROOK_OFFLINE=1` forbids Meta calls even with a key present (`docs/FIRST_RUN.md`, offline enforcement tests) |
| No silent cloud escalation | Switching from local to cloud needs an explicit user decision (provider-switch privacy tests, M016 suite, still green) |

## 2. Screenshots

- Consent gate: `POST /api/investigations` and turn endpoints return
  HTTP 400 when image bytes arrive without `share_consent`
  (`backend/app/routers/investigations.py`, consent tests).
- No persistence: only metadata (filename, mime, byte count) is kept
  as evidence; the API records "FieldRook does not store it" on the
  evidence item and in warnings (same file).
- Transmission is labeled: the evidence note names the processing
  location (local vs cloud) chosen with consent.

## 3. Collector packages (untrusted input)

- Import requires `share_consent=true` (HTTP 400 otherwise) and
  rejects non-ZIP uploads (`test_forge_wiring.py`, ZETA probes).
- Packages are validated atomically: traversal, symlink/device/fifo,
  per-file (2MB), total (20MB), file-count (200), compression-ratio,
  hash-mismatch, unlisted/missing members all reject the whole import
  with no partial ingest (`collector/archive.py` + 25 archive tests).
- Identity minimization: raw hostnames never persist; imports keep
  `hostname_hash` + optional sanitized hint only (D8,
  `collector/redact_import.py`, ZETA `wrong_host` behavior).
- Content redaction at import: secrets, emails, `DOMAIN\user`, OS
  username, and command lines are redacted or dropped with counts in
  provenance (`redact_import.py`, redaction tests, roundtrip test
  asserting no raw secrets/hostname in packages).

## 4. Knowledge and reference

- Case memory is local SQLite only; matches are computed
  deterministically in-process. The only model contact is a
  technician-initiated follow-up carrying a short templated prompt,
  never the library (`backend/app/routers/knowledge.py` docstring).
- Reference excerpts reach the model exclusively as quoted blocks on
  user-role messages, never as system instructions
  (`build_knowledge_context` + M022 test pinning system-message
  cleanliness; injection-probe ZETA case passes).
- Reference spans are pre-redacted by `match_references` before any
  turn or endpoint use.

## 5. Turn context and export

- Turn text is redacted before model contact
  (`test_turn_text_is_redacted` and the M016 privacy suite, green).
- Fabricated citations cannot survive: `validate_assessment_output`
  drops evidence ids outside the known set (`_known_only`,
  `backend/app/analysis/validate.py`).
- Exports (Markdown/JSON) contain the case record including
  provenance; they are operator-initiated downloads, never uploaded.

## 6. Secrets hygiene

- `git diff master...forge/integration` scanned twice (M020 ZETA,
  M024 gate): only synthetic redaction fixtures; no key blocks, token
  prefixes, or private keys.
- No `.env` or credential files tracked; `.env` paths are git-ignored.
- The release launcher (`start-fieldrook.bat`) embeds no keys and
  copies no operator `.env`; live-model use still requires the
  operator's own explicit key setup per `docs/FIRST_RUN.md`.

## 7. Residual privacy risks

- Imported collector `notes/` payloads are operator-attached text;
  redaction covers known patterns, not arbitrary prose secrets.
- Export files are only as safe as the operator's ticket system.
- Screenshot bytes transit to the selected provider with consent;
  provider-side retention follows that provider's policy, not ours.
