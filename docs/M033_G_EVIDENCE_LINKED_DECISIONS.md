# M033-G — Evidence-Linked Hypothesis Decisions

**Date:** 2026-11-18
**Development branch:** m033/evidence-linked-decisions
**Parent:** M033-F 8c31287
**Published release:** v0.6.0-rc.2 remains untouched. No merge, push or packaging.

## Goal

A hypothesis transition is a decision, not an evidence item. A model can
state that "Driver conflict is less likely" after reading "Windows installed
a new network driver"; the existence of an evidence ID cannot itself prove
that inference.

M033-G introduces an **append-only hypothesis decision journal**, linking
each LOCAL-model-proposed weakening to its source references and recording
whether a technician explicitly reviewed it. A valid reference establishes
only **source identity**, not causal entailment.

## Modes

Use FIELDROOK_HYPOTHESIS_DECISION_MODE:

- **observe** (default): record model proposals and validate source IDs.
  The normal M033-F hypothesis merge behavior remains unchanged. Existing
  M033-B's no-information hard guard still protects missing-information
  responses. Use to gather non-invasive review data.
- **require_review** (experimental, opt-in): model-proposed weakening is
  removed from the assessment before model suggestions can be merged.
  The original model response is not mutated. A decision-journal entry is
  recorded as pending_technician and the next safe question/check remains
  available. A technician can use the existing "Record your judgment"
  control on the hypothesis to explicitly mark weakened, ruled out,
  confirmed or reopened. That updates only the most recent pending
  proposal for that hypothesis to technician_applied / technician_overrode.
  Deterministic contradiction/refresh rules are independent and unchanged.
- **off**: no M033-G journal or new gating. Legacy investigation behavior
  is preserved, with the separate M033-B rules still in force.

Unrecognized mode values fall back to observe. No extra AI calls or
automatic host actions were added. M033-C/F separate observe/enforce
settings are unaffected.

## Source types and limits

The journal records structured source status:

- **Valid collected evidence**: only IDs actually present in the same
  investigation; successful nonempty records, not failed collectors.
- **Measured host evidence**: an additional subset of valid items produced
  by an authorized host-tool source. A remote-target investigation must
  never treat FieldRook's own local readings as measurements of another PC.
- **Technician reports**: report:N means the Nth zero-based message in
  the investigation was a nonempty user text turn. The report remains
  *reported*, not an observed host measurement. These references are
  stable across SQLite restarts and cannot be invented by the model.
- **Fixture or other import**: may be a valid record but is never
  mislabeled as a live host measurement.
- **Rejected references**: unknown, malformed, failed/empty,
  superseded readings, wrong-host readings, or invalid report references.
  A rejected reference cannot be laundered into an evidence link.
- **Uncited**: a valid model-generated suggestion without any valid
  source; it stays labeled uncited, not unverified-in-secret.

Even a perfectly valid evidence ID only indicates that the source exists.
The journal never claims that it logically confirms or contradicts a cause.

Source lists, titles, and reasons are bounded. A source audit does not
persist screenshots, raw tool outputs or technician text a second time.
All existing data protection and operator-consent checks remain unchanged.

## Data model

New Pydantic HypothesisDecisionRecord fields:

- decision_id, round, hypothesis_id, hypothesis_title, proposed_status
- reason (model-supplied, untrusted)
- evidence_ids (validated existing sources)
- measured_evidence_ids (subset of valid host-tool readings)
- report_refs (validated technician text turns)
- rejected_refs (safe failure-code labels, never invented IDs)
- link_status (uncited, invalid, report_only, evidence_cited, mixed)
- review_state (observed, pending_technician, technician_applied,
  technician_overrode)
- provenance_note (explicit warning: source citations are not proof)

Records persist inside the existing versioned assist JSON document in
SQLite without requiring a destructive database migration. Older stored
investigations without this field open with an empty decision journal.

An optional model JSON field, decision_links, is used only for LOCAL
reassessment in the experimental require_review mode. It has a bounded
shape: hypothesis, evidence_ids, report_refs, why. Existing default
prompts remain unchanged. Missing or malformed links never crash the
analysis; they become uncited or invalid audit entries.

## UI

The Guided Investigation panel shows a "Hypothesis decision journal"
above hypothesis cards, up to the most recent twelve entries. Every entry
shows proposed status, review state, source-validation status, source
chips (clickable evidence IDs), reported-turn references, rejected-ref
reason codes and an explicit note that citations are not proof.

Existing "Record your judgment" in a hypothesis card is the approval
point. The journal does not auto-approve a proposal because an evidence
record is present or a model sounds confident.

## Tests and verification

New tests cover valid, missing and forged source IDs; failed, empty,
superseded and wrong-host evidence; reports vs measurements; malformed
model output; repeat titles; unchanged default behavior; explicit
review holding; manual acceptance and override; record persistence
across SQLite reload; API response serialization; original no-info
protection and actual local task-loop integration.

Verification on Fury (2026-11-18):
- Full backend suite: **896 passed, 4 skipped, 0 failed**, 2 warnings
  (initial full run, before the final manual-judgment and redaction hardening).
- Post-hardening cross-regression: **166 passed, 0 failed** in
  test_assist.py, test_local_tasks.py, test_evidence_integrity.py and
  test_hypothesis_decisions.py.
- Latest final-code M033-G/M033-F loop regression: **87 passed, 0 failed**
  after preserving raw model proposals for evidence-integrity auditing.
- M033-G direct backend tests: **25 passed**, including an actual API
  same-status override, SQLite reload and model-reason secret redaction.
- Frontend: `npm run build` passed (TypeScript checking + Vite build).
- M033-G Playwright UI smoke: **1 passed** against a real isolated
  fixture backend plus an injected decision record.
- Full Playwright E2E suite: **99 passed, 0 failed**, using isolated
  real backend and Vite servers (297.90s).
- `git diff --check` clean; no push, merge, release or rc.2 change.

Additional hardening:
- A technician can explicitly accept/override a pending model proposal
  even if the selected status equals the current hypothesis state. The
  explicit re-affirmation is recorded in history, preserving the manual
  lock against later model overrides. Without a pending review, an
  unchanged status retains the pre-existing no-op semantics.
- Persisted model-supplied `why` text now passes existing secret,
  username and email redaction before being bounded to 500 characters.
- M033-F evaluates the guarded, original model proposal before M033-G's
  require_review projection removes unsafe `weakened` transitions from
  state merging. A held proposal can therefore still trigger the
  correlated-change-weakened warning; covered by regression.

## Remaining limitations

- Source identity is not a reliable semantic entailment checker.
  Valid ev-N citations may be irrelevant to the proposed cause.
- The interface does not certify the correctness of any proposed
  weakening or prove a root cause by itself.
- The opt-in review gate is currently for LOCAL model reassessment.
  Meta/live route and legacy deterministic rules have not been
  silently changed.
- Only explicit model-proposed weakening is journaled by this step;
  later releases should cover confirm / rule-out / strengthen
  transitions separately, with explicit technician decision paths.
- Technical review or a new benchmark with blinded technician
  grading is required before require_review becomes a default.
