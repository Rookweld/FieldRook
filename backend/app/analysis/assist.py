"""M016 adaptive investigation engine: hypotheses, plans, questions, stages.

The assist layer turns each accepted assessment into a living troubleshooting
workflow. Model suggestions are untrusted input: they arrive through lenient
validators and are merged here with deterministic signals (contradictions,
refresh verdicts, recheck rankings, technician turns) into versioned,
evidence-linked domain objects. History is append-only: hypotheses are never
rewritten, plan outcomes are never discarded, answered questions are never
asked again.

Two reasoning tiers, honestly separated:
- Live providers propose hypotheses/plans/questions; the engine validates,
  evidence-checks, and merges them.
- Simulated mode builds the same structures deterministically from causes,
  contradictions, refreshes, and rechecks, and never invents model judgment
  (it weakens hypotheses on contradictory readings but never rules them out
  on its own; that needs a technician or a live model round).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..schemas import (
    ClarifyingQuestion,
    Hypothesis,
    HypothesisEvent,
    SuggestedHypothesis,
    SuggestedPlanStep,
    SuggestedQuestion,
    TroubleshootPlan,
    TroubleshootStep,
)

if TYPE_CHECKING:
    from ..investigations.store import InvestigationState

MAX_HYPOTHESES = 8
MAX_PLAN_STEPS = 6


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _new_id(state: InvestigationState, kind: str) -> str:
    counters = state.assist_counters
    counters[kind] = int(counters.get(kind, 0)) + 1
    prefix = {"hyp": "hyp", "step": "step", "q": "q"}.get(kind, kind)
    return f"{prefix}-{counters[kind]}"


# ---------------------------------------------------------------------------
# Hypotheses
# ---------------------------------------------------------------------------


def _suggested_or_causes(state: InvestigationState) -> list[SuggestedHypothesis]:
    """Model suggestions win; otherwise derive tracking entries from causes."""
    assessment = state.assessment
    if assessment is None:
        return []
    if assessment.suggested_hypotheses:
        return list(assessment.suggested_hypotheses)
    derived: list[SuggestedHypothesis] = []
    for cause in assessment.causes[:MAX_HYPOTHESES]:
        if not (cause.title or "").strip():
            continue
        derived.append(
            SuggestedHypothesis(
                title=cause.title.strip(),
                description=cause.description or "",
                status="active",
                supporting_evidence_ids=list(cause.evidence_ids),
                contradicting_evidence_ids=[],
            )
        )
    return derived


def _set_hypothesis_status(
    hyp: Hypothesis, status: str, reason: str, round_no: int
) -> bool:
    if hyp.status == status:
        return False
    hyp.status = status  # type: ignore[assignment]
    hyp.updated_round = round_no
    hyp.history.append(HypothesisEvent(round=round_no, status=status, reason=reason[:500]))  # type: ignore[arg-type]
    return True


def merge_hypotheses(state: InvestigationState, round_no: int) -> list[str]:
    """Merge suggested/derived hypotheses into tracked, versioned entries.

    Returns short change notes for activity records. Deterministic
    contradiction/refresh signals weaken hypotheses; only an explicit model
    status or a technician turn retires one (see mark_hypothesis).
    """
    from ..analysis.contradictions import detect_contradictions

    notes: list[str] = []
    suggested = _suggested_or_causes(state)
    known = state.known_evidence_ids()
    by_title = {_normalize(h.title): h for h in state.hypotheses}
    for item in suggested:
        title = (item.title or "").strip()
        if not title:
            continue
        key = _normalize(title)
        existing = by_title.get(key)
        supporting = [eid for eid in item.supporting_evidence_ids if eid in known]
        contradicting = [eid for eid in item.contradicting_evidence_ids if eid in known]
        if existing is None:
            if len(state.hypotheses) >= MAX_HYPOTHESES:
                continue
            hyp = Hypothesis(
                hypothesis_id=_new_id(state, "hyp"),
                title=title,
                description=(item.description or "").strip()[:2000],
                status="active",
                supporting_evidence_ids=supporting,
                contradicting_evidence_ids=contradicting,
                created_round=round_no,
                updated_round=round_no,
                history=[HypothesisEvent(round=round_no, status="active", reason="Hypothesis recorded.")],
            )
            state.hypotheses.append(hyp)
            by_title[key] = hyp
            notes.append(f"new: {title}")
            continue
        if item.description and item.description.strip() != existing.description:
            existing.description = item.description.strip()[:2000]
            existing.updated_round = round_no
        merged_support = list(dict.fromkeys([*existing.supporting_evidence_ids, *supporting]))
        merged_contra = list(dict.fromkeys([*existing.contradicting_evidence_ids, *contradicting]))
        if merged_support != existing.supporting_evidence_ids:
            existing.supporting_evidence_ids = merged_support
            existing.updated_round = round_no
        if merged_contra != existing.contradicting_evidence_ids:
            existing.contradicting_evidence_ids = merged_contra
            existing.updated_round = round_no
        # A live model may retire or confirm its own hypotheses; simulated
        # derivations always arrive "active", so they never override status.
        # Explicit technician judgments (history reason "Technician ...")
        # are never overridden by the model.
        locked = bool(existing.history) and existing.history[-1].reason.startswith("Technician ")
        if (
            state.assessment is not None
            and state.assessment.suggested_hypotheses
            and not locked
        ):
            if item.status != existing.status and item.status in ("weakened", "ruled_out", "confirmed"):
                if _set_hypothesis_status(
                    existing, item.status,
                    f"Model reassessment in round {round_no}.", round_no,
                ):
                    notes.append(f"{existing.status}: {existing.title}")
    # Deterministic weakening from contradiction rules.
    contradictions = detect_contradictions(state.problem, list(state.evidence))
    for hyp in state.hypotheses:
        if hyp.status in ("ruled_out", "confirmed"):
            continue
        for contra in contradictions:
            conflicted = set(contra.evidence_ids) & set(hyp.supporting_evidence_ids)
            if conflicted:
                if _set_hypothesis_status(
                    hyp, "weakened",
                    f"Contradicted by {contra.contradiction_id}: {contra.description}",
                    round_no,
                ):
                    notes.append(f"weakened: {hyp.title}")
                break
    # Deterministic weakening when supporting readings were superseded.
    for refresh in state.refreshes:
        if refresh.verdict not in ("changed", "unavailable"):
            continue
        for hyp in state.hypotheses:
            if hyp.status in ("ruled_out", "confirmed"):
                continue
            if refresh.old_evidence_id in hyp.supporting_evidence_ids:
                label = refresh.new_evidence_id or "rerun failed"
                if _set_hypothesis_status(
                    hyp, "weakened",
                    f"Built on superseded reading {refresh.old_evidence_id} "
                    f"({refresh.verdict} in {label}).",
                    round_no,
                ):
                    notes.append(f"weakened: {hyp.title}")
    return notes


def mark_hypothesis(
    state: InvestigationState, hypothesis_id: str, status: str, reason: str, round_no: int
) -> bool:
    """Technician- or turn-driven status change with preserved history."""
    if status not in ("active", "weakened", "ruled_out", "confirmed"):
        return False
    hyp = next((h for h in state.hypotheses if h.hypothesis_id == hypothesis_id), None)
    if hyp is None:
        return False
    return _set_hypothesis_status(hyp, status, reason, round_no)


# ---------------------------------------------------------------------------
# Troubleshooting plans
# ---------------------------------------------------------------------------


def _downgrade_for_target(step: SuggestedPlanStep, target: str) -> SuggestedPlanStep:
    """Non-local targets cannot use host measurements: rewrite as guidance."""
    if target == "local" or step.kind != "AUTOMATED_READ_ONLY":
        return step
    return SuggestedPlanStep(
        instruction=f"On the affected computer: {step.instruction}",
        why=(step.why + " (FieldRook cannot measure another computer itself.)").strip(),
        kind="TECHNICIAN_CHECK",
        tool_name=None,
        expected_observations=list(step.expected_observations),
        admin_maybe=step.admin_maybe,
    )


def _deterministic_steps(state: InvestigationState) -> list[SuggestedPlanStep]:
    """Simulated-mode plan from rechecks, contradictions, and open questions."""
    from ..analysis.contradictions import detect_contradictions
    from ..analysis.loop import MAX_TOOL_CALLS
    from ..analysis.rechecks import suggest_rechecks
    from ..config import load_settings
    from ..tools.registry import REGISTRY

    try:
        ttl_s = load_settings().evidence_ttl_s
    except Exception:  # noqa: BLE001 - plan building must not fail
        ttl_s = 900.0
    steps: list[SuggestedPlanStep] = []
    remote = state.target != "local"
    budget_left = MAX_TOOL_CALLS - state.tool_calls_made
    for recheck in suggest_rechecks(state, ttl_s, MAX_TOOL_CALLS)[:3]:
        spec = REGISTRY.get(recheck.tool_name)
        if spec is None:
            continue
        if remote or budget_left <= 0:
            steps.append(
                SuggestedPlanStep(
                    instruction=(
                        f"On the affected computer, re-check the {spec.category} reading "
                        f"behind {recheck.evidence_id} and report what you see."
                    ),
                    why=recheck.reason,
                    kind="TECHNICIAN_CHECK",
                    expected_observations=[
                        "Same reading: the earlier evidence still holds.",
                        "Different reading: hypotheses built on it need review.",
                    ],
                )
            )
        else:
            steps.append(
                SuggestedPlanStep(
                    instruction=f"Re-check {recheck.evidence_id} with {recheck.tool_name}.",
                    why=recheck.reason,
                    kind="AUTOMATED_READ_ONLY",
                    tool_name=recheck.tool_name,
                    expected_observations=[
                        "Unchanged: the earlier evidence still holds.",
                        "Changed: hypotheses built on it need review.",
                    ],
                )
            )
    for contra in detect_contradictions(state.problem, list(state.evidence))[:1]:
        steps.append(
            SuggestedPlanStep(
                instruction=(
                    f"Compare {', '.join(contra.evidence_ids)}: {contra.description} "
                    "Determine which reading reflects the current state."
                ),
                why="Contradictory readings cannot both be current; one needs a tie-breaker.",
                kind="TECHNICIAN_CHECK",
                expected_observations=[
                    "One reading is stale or misread: follow the current one.",
                    "Both hold at different times: the state may be flapping.",
                ],
            )
        )
    for question in [q for q in state.questions if q.status == "open"][:2]:
        steps.append(
            SuggestedPlanStep(
                instruction=f"Answer: {question.question}",
                why=question.why or "The answer decides the next diagnostic step.",
                kind="CLARIFYING_QUESTION",
            )
        )
    if state.assessment is not None and not steps:
        for missing in state.assessment.missing_evidence[:2]:
            steps.append(
                SuggestedPlanStep(
                    instruction=f"Collect or describe: {missing}",
                    why="This evidence would distinguish between the open hypotheses.",
                    kind="TECHNICIAN_CHECK",
                )
            )
    return steps[:MAX_PLAN_STEPS]


def merge_plan(state: InvestigationState, round_no: int) -> str:
    """Merge suggested/deterministic steps into the living plan.

    Terminal steps (done/blocked) and their outcomes are always preserved;
    open steps are matched by instruction so ids stay stable across rounds.
    Returns a one-line summary for the activity record.
    """
    from ..tools.registry import REGISTRY

    if state.plan is None:
        state.plan = TroubleshootPlan(plan_id=f"tplan-{state.id}", updated_round=round_no)
    plan = state.plan
    suggested: list[SuggestedPlanStep] = []
    if state.assessment is not None and state.assessment.suggested_plan is not None:
        suggested = [_downgrade_for_target(s, state.target) for s in state.assessment.suggested_plan.steps]
    if not suggested:
        suggested = [_downgrade_for_target(s, state.target) for s in _deterministic_steps(state)]
    kept: list[TroubleshootStep] = [s for s in plan.steps if s.status in ("done", "blocked")]
    kept_keys = {_normalize(s.instruction) for s in kept}
    open_existing = {_normalize(s.instruction): s for s in plan.steps if s.status in ("suggested", "current")}
    merged: list[TroubleshootStep] = list(kept)
    for item in suggested[:MAX_PLAN_STEPS]:
        instruction = (item.instruction or "").strip()
        if not instruction or _normalize(instruction) in kept_keys:
            continue
        match = open_existing.pop(_normalize(instruction), None)
        if match is not None:
            if item.why:
                match.why = item.why[:1000]
            if item.expected_observations:
                match.expected_observations = [o[:500] for o in item.expected_observations[:6]]
            if item.kind:
                match.kind = item.kind
            if item.tool_name and item.tool_name in REGISTRY:
                match.tool_name = item.tool_name
            match.admin_maybe = bool(item.admin_maybe)
            merged.append(match)
            continue
        tool_name = item.tool_name if item.tool_name in REGISTRY else None
        merged.append(
            TroubleshootStep(
                step_id=_new_id(state, "step"),
                instruction=instruction[:1000],
                why=(item.why or "")[:1000],
                kind=item.kind,
                status="suggested",
                tool_name=tool_name,
                expected_observations=[o[:500] for o in item.expected_observations[:6]],
                admin_maybe=bool(item.admin_maybe),
            )
        )
    # Open steps the new direction no longer mentions are kept as skipped
    # history, never silently dropped.
    for leftover in open_existing.values():
        leftover.status = "skipped"
        if not leftover.outcome:
            leftover.outcome = "Superseded by a plan update."
        merged.append(leftover)
    # Cap open steps; terminal history is never trimmed.
    open_merged = [s for s in merged if s.status in ("suggested", "current")]
    if len(open_merged) > MAX_PLAN_STEPS:
        drop_ids = {s.step_id for s in open_merged[MAX_PLAN_STEPS:]}
        merged = [s for s in merged if s.step_id not in drop_ids]
    plan.steps = merged
    plan.updated_round = round_no
    current = next((s for s in merged if s.status == "current"), None)
    if current is None:
        nxt = next((s for s in merged if s.status == "suggested"), None)
        if nxt is not None:
            nxt.status = "current"
            current = nxt
    plan.current_step_id = current.step_id if current is not None else None
    if current is not None:
        return f"{len(merged)} step(s); current: {current.instruction[:120]}"
    if kept:
        return f"{len(merged)} step(s); all terminal, awaiting a new direction."
    return "No steps: nothing left to suggest from current evidence."


def current_step(state: InvestigationState) -> TroubleshootStep | None:
    if state.plan is None:
        return None
    for step in state.plan.steps:
        if step.step_id == state.plan.current_step_id:
            return step
    return next((s for s in state.plan.steps if s.status in ("current", "suggested")), None)


# ---------------------------------------------------------------------------
# Clarifying questions
# ---------------------------------------------------------------------------

TARGET_QUESTION = "Is the affected computer this one (where FieldRook runs) or a different machine?"


def _question_exists(state: InvestigationState, text: str) -> bool:
    needle = _normalize(text)
    if not needle:
        return True
    for existing in state.questions:
        hay = _normalize(existing.question)
        if not hay:
            continue
        if needle == hay or needle in hay or hay in needle:
            return True
    return False


def merge_questions(state: InvestigationState) -> list[str]:
    """Adopt suggested questions; never repeat an asked one. Returns new ids."""
    added: list[str] = []
    suggested = (
        list(state.assessment.suggested_questions)
        if state.assessment is not None
        else []
    )
    if state.target == "unknown" and not _question_exists(state, TARGET_QUESTION):
        suggested.insert(
            0,
            SuggestedQuestion(
                question=TARGET_QUESTION,
                why="Local diagnostics only describe this computer; the plan depends on the answer.",
            ),
        )
    for item in suggested:
        text = (item.question or "").strip()
        if not text or _question_exists(state, text):
            continue
        question = ClarifyingQuestion(
            question_id=_new_id(state, "q"),
            question=text[:1000],
            why=(item.why or "").strip()[:1000],
            status="open",
        )
        state.questions.append(question)
        added.append(question.question_id)
    # Simulated fallback: turn missing evidence into at most two open asks.
    if state.assessment is not None and not any(q.status == "open" for q in state.questions):
        for missing in state.assessment.missing_evidence[:2]:
            text = f"Can you provide or check the following: {missing}"
            if _question_exists(state, text):
                continue
            question = ClarifyingQuestion(
                question_id=_new_id(state, "q"),
                question=text[:1000],
                why="This would distinguish between the open hypotheses.",
                status="open",
            )
            state.questions.append(question)
            added.append(question.question_id)
            if len(added) >= 2:
                break
    return added


# ---------------------------------------------------------------------------
# Stage + master refresh
# ---------------------------------------------------------------------------


def compute_stage(state: InvestigationState) -> str:
    """Deterministic lifecycle stage from persisted signals (no guessing)."""
    for proposal in state.proposals:
        if proposal.status == "VERIFIED_RESOLVED":
            return "RESOLVED"
    for plan in state.plans:
        if plan.status == "VERIFIED_RESOLVED":
            return "RESOLVED"
    for proposal in state.proposals:
        if proposal.status in ("APPROVED", "EXECUTING", "EXECUTED_UNVERIFIED"):
            return "VERIFYING"
    for plan in state.plans:
        if plan.status in ("BASELINED", "INTERVENED"):
            return "VERIFYING"
    for proposal in state.proposals:
        if proposal.status in ("PROPOSED", "AWAITING_APPROVAL"):
            return "READY_TO_RESOLVE"
    for plan in state.plans:
        if plan.status == "DRAFT" and plan.criteria:
            return "READY_TO_RESOLVE"
    if state.blocked_reason:
        return "BLOCKED"
    if state.assessment is None:
        return "INTAKE"
    if any(q.status == "open" for q in state.questions):
        return "CLARIFYING"
    if state.activity and state.activity[-1].kind == "turn":
        return "REASSESSING"
    if state.plan is not None and any(s.status == "done" for s in state.plan.steps):
        return "INVESTIGATING"
    if state.plan is not None:
        return "PLANNING"
    return "INVESTIGATING"


def refresh_assist(state: InvestigationState, round_no: int) -> None:
    """Master hook after every accepted/substituted assessment."""
    if state.assessment is not None and state.assessment.understanding.strip():
        state.understanding = state.assessment.understanding.strip()[:2000]
    hyp_notes = merge_hypotheses(state, round_no)
    if hyp_notes:
        shown = "; ".join(hyp_notes[:3])
        if len(hyp_notes) > 3:
            shown += f" (+{len(hyp_notes) - 3} more)"
        state.add_activity("hypothesis", "Hypotheses updated", shown)
    plan_summary = merge_plan(state, round_no)
    state.add_activity("troubleshoot_plan", "Troubleshooting plan updated", plan_summary)
    new_questions = merge_questions(state)
    for question_id in new_questions:
        question = next(q for q in state.questions if q.question_id == question_id)
        state.add_activity("question", "Clarifying question", question.question[:300])


def latest_assistant_message(state: InvestigationState) -> str:
    """Most recent assistant text for the conversation view (never raw JSON).

    Assessment payloads surface their summary; reasoning notes surface
    trimmed. Empty when the provider produced no displayable text.
    """
    import json as _json

    for message in reversed(state.messages):
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        text = content if isinstance(content, str) else ""
        if not text.strip():
            continue
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                payload = _json.loads(stripped)
            except ValueError:
                payload = None
            if isinstance(payload, dict) and payload.get("summary"):
                return str(payload["summary"])[:1500]
            continue
        return stripped[:1500]
    return ""


def describe_state(state: InvestigationState) -> dict[str, Any]:
    """Compact assist snapshot for exports and evaluations."""
    step = current_step(state)
    return {
        "stage": compute_stage(state),
        "target": state.target,
        "understanding": state.understanding,
        "hypotheses": [
            {"id": h.hypothesis_id, "title": h.title, "status": h.status}
            for h in state.hypotheses
        ],
        "open_questions": [q.question for q in state.questions if q.status == "open"],
        "current_step": step.instruction if step else None,
        "rounds_used": state.rounds_used,
        "blocked_reason": state.blocked_reason,
    }
