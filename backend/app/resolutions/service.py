"""Resolution plans and guided Confirm Fix verification.

A plan turns evidence-backed findings into explicit, measurable success
criteria. Confirm Fix captures a pre-fix baseline, waits for a recorded
intervention (a real authorized execution or a technician-confirmed manual
claim), re-runs the criterion diagnostics, and grades the outcome purely
from fresh measurements:

- VERIFIED_RESOLVED: every criterion passes on fresh evidence.
- NOT_RESOLVED: at least one criterion is contradicted by measurement.
- INCONCLUSIVE: tool failures or missing paths prevent a verdict.

A manual "done" records a claim, never proof. Verification only ever runs
registered read-only diagnostics: it cannot authorize or execute actions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..actions.registry import get_action as get_action_spec
from ..actions.registry import UnknownActionError
from ..analysis.loop import MAX_TOOL_CALLS
from ..analysis.refresh import compare_readings
from ..config import Settings
from ..schemas import (
    CriterionResult,
    PlanIntervention,
    PlanVerification,
    ResolutionCriterion,
    ResolutionPlan,
)
from ..tools.registry import (
    REGISTRY,
    ToolCallError,
    ToolContext,
    execute_prepared,
    prepare_call,
)

MAX_CRITERIA = 8


class PlanError(ValueError):
    """Invalid plan request or plan state for the requested step."""


class PlanBudgetError(PlanError):
    """Not enough diagnostic budget left for baseline/verification."""


_MISSING = object()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def plan_template(action_id: str) -> dict[str, Any]:
    """Suggested criteria for a registered action (its documented checks)."""
    try:
        spec = get_action_spec(action_id)
    except UnknownActionError as exc:
        raise PlanError(f"Unknown action {action_id!r}.") from exc
    if action_id == "recover_demo_worker":
        return {
            "action_id": spec.id,
            "target": sorted(spec.targets)[0],
            "intended_state": spec.expected_result,
            "guidance": (
                "Approve and execute the registered demo-worker recovery, "
                "then Confirm Fix. FieldRook re-reads worker health and grades "
                "the criteria below from fresh measurements."
            ),
            "risks": (
                "Low: the recovery only touches application-owned demo-worker "
                "state and its own verified process. " + spec.verification_method
            ),
            "criteria": [
                {
                    "description": "Worker status reads healthy.",
                    "tool_name": "get_demo_worker_health",
                    "tool_args": {},
                    "path": "status",
                    "op": "eq",
                    "expected": "healthy",
                },
                {
                    "description": "Worker heartbeat is fresh (under 10s old).",
                    "tool_name": "get_demo_worker_health",
                    "tool_args": {},
                    "path": "heartbeat_age_s",
                    "op": "lt",
                    "expected": 10,
                },
            ],
        }
    raise PlanError(f"No plan template for action {action_id!r}.")


def _check_path(path: str) -> list[str]:
    segments = (path or "").strip().split(".")
    if not segments or any(not seg for seg in segments):
        raise PlanError(f"Invalid criterion path {path!r}: use dot-separated names.")
    for seg in segments:
        if not seg.replace("_", "").replace("-", "").isalnum():
            raise PlanError(f"Invalid criterion path {path!r}: bad segment {seg!r}.")
    if len(segments) > 8:
        raise PlanError(f"Invalid criterion path {path!r}: too deep.")
    return segments


def resolve_path(data: Any, path: str) -> Any:
    current = data
    for seg in _check_path(path):
        if isinstance(current, dict):
            if seg not in current:
                return _MISSING
            current = current[seg]
        elif isinstance(current, list) and seg.isdigit():
            index = int(seg)
            if index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate(op: str, observed: Any, expected: Any) -> tuple[str, str]:
    """Grade one observation. Returns (pass|fail|inconclusive, detail)."""
    if observed is _MISSING or observed is None:
        if op == "exists":
            return "fail", "path is absent."
        return "inconclusive", "path is absent from the tool output."
    if op == "exists":
        return "pass", f"observed {observed!r}."
    if op == "eq":
        ok = bool(observed == expected)
        return ("pass" if ok else "fail"), f"observed {observed!r}, expected {expected!r}."
    if op == "ne":
        ok = bool(observed != expected)
        return ("pass" if ok else "fail"), f"observed {observed!r}, must differ from {expected!r}."
    if op == "contains":
        if isinstance(observed, list):
            ok = expected in observed
        else:
            ok = str(expected) in str(observed)
        return ("pass" if ok else "fail"), f"observed {observed!r}, must contain {expected!r}."
    if op in ("gt", "gte", "lt", "lte"):
        if not _is_number(observed) or not _is_number(expected):
            return "inconclusive", f"non-numeric comparison: {observed!r} {op} {expected!r}."
        checks = {
            "gt": observed > expected,
            "gte": observed >= expected,
            "lt": observed < expected,
            "lte": observed <= expected,
        }
        ok = bool(checks[op])
        return ("pass" if ok else "fail"), f"observed {observed!r} {op} {expected!r}."
    return "inconclusive", f"unknown operator {op!r}."


def create_plan(state: Any, payload: dict[str, Any]) -> ResolutionPlan:
    known = {item.id for item in state.evidence}
    evidence_ids = payload.get("evidence_ids", [])
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise PlanError("A plan needs at least one supporting evidence id.")
    unknown = [eid for eid in evidence_ids if eid not in known]
    if unknown:
        raise PlanError(f"Unknown evidence ids: {', '.join(sorted(set(unknown)))}.")
    intended = str(payload.get("intended_state", "") or "").strip()
    if len(intended) < 10:
        raise PlanError("intended_state must describe the healthy state (>= 10 chars).")
    raw_criteria = payload.get("criteria", [])
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise PlanError("A plan needs at least one measurable criterion.")
    if len(raw_criteria) > MAX_CRITERIA:
        raise PlanError(f"A plan holds at most {MAX_CRITERIA} criteria.")
    criteria: list[ResolutionCriterion] = []
    for index, raw in enumerate(raw_criteria):
        if not isinstance(raw, dict):
            raise PlanError(f"Criterion #{index + 1} must be an object.")
        description = str(raw.get("description", "") or "").strip()
        if not description:
            raise PlanError(f"Criterion #{index + 1} needs a description.")
        tool_name = raw.get("tool_name")
        if tool_name not in REGISTRY:
            raise PlanError(f"Criterion #{index + 1}: unknown tool {tool_name!r}.")
        try:
            _spec, args = prepare_call(tool_name, raw.get("tool_args", {}) or {})
        except ToolCallError as exc:
            raise PlanError(f"Criterion #{index + 1}: {exc}") from exc
        _check_path(str(raw.get("path", "") or ""))
        op = raw.get("op")
        if op not in ("eq", "ne", "contains", "gt", "gte", "lt", "lte", "exists"):
            raise PlanError(f"Criterion #{index + 1}: unknown operator {op!r}.")
        criteria.append(
            ResolutionCriterion(
                criterion_id=f"crit-{uuid4().hex[:8]}",
                description=description[:500],
                tool_name=str(tool_name),
                tool_args=args.model_dump(mode="json"),
                path=str(raw.get("path", "")).strip(),
                op=op,  # type: ignore[arg-type]
                expected=raw.get("expected"),
            )
        )
    remediation_kind = payload.get("remediation_kind", "manual")
    if remediation_kind not in ("manual", "action"):
        raise PlanError("remediation_kind must be 'manual' or 'action'.")
    action_id = payload.get("action_id")
    target = payload.get("target")
    if remediation_kind == "action":
        from ..actions.policies import actions_enabled

        try:
            spec = get_action_spec(action_id)
        except UnknownActionError as exc:
            raise PlanError(f"Unknown action {action_id!r}.") from exc
        if not actions_enabled() or not spec.enabled:
            raise PlanError(f"Action '{spec.id}' is disabled in this environment.")
        if not isinstance(target, str) or target not in spec.targets:
            raise PlanError(f"Target {target!r} is not allowed for '{spec.id}'.")
    elif action_id is not None or target is not None:
        raise PlanError("Manual plans must not name an action or target.")
    plan = ResolutionPlan(
        plan_id=f"plan-{uuid4().hex[:12]}",
        investigation_id=state.id,
        problem=str(payload.get("problem", "") or state.problem)[:2000],
        evidence_ids=list(evidence_ids),
        intended_state=intended[:2000],
        criteria=criteria,
        guidance=str(payload.get("guidance", "") or "")[:2000],
        risks=str(payload.get("risks", "") or "")[:2000],
        remediation_kind=remediation_kind,  # type: ignore[arg-type]
        action_id=action_id if remediation_kind == "action" else None,
        target=target if remediation_kind == "action" else None,
        created_at=_now(),
    )
    state.plans.append(plan)
    state.add_activity(
        "note", f"Resolution plan {plan.plan_id} drafted",
        f"{len(criteria)} criteria; remediation: {remediation_kind}.",
        evidence_ids=list(evidence_ids),
    )
    return plan


def _unique_calls(criteria: list[ResolutionCriterion]) -> list[tuple[str, dict[str, Any]]]:
    seen: dict[str, tuple[str, dict[str, Any]]] = {}
    for criterion in criteria:
        import json as _json

        key = criterion.tool_name + ":" + _json.dumps(criterion.tool_args, sort_keys=True, default=str)
        seen.setdefault(key, (criterion.tool_name, criterion.tool_args))
    return list(seen.values())


async def _run_criterion_tools(
    state: Any, plan: ResolutionPlan, settings: Settings, use_fixtures: bool | None, label: str
) -> dict[str, Any]:
    """Run each distinct criterion tool once; returns key -> (evidence_item, output)."""
    from ..analysis.loop import _call_signature  # reuse M007 signature helper

    ctx = ToolContext(settings=settings, use_fixtures=use_fixtures)
    calls = _unique_calls(plan.criteria)
    if state.tool_calls_made + len(calls) > MAX_TOOL_CALLS:
        raise PlanBudgetError(
            f"Plan {label} needs {len(calls)} diagnostic call(s) but only "
            f"{MAX_TOOL_CALLS - state.tool_calls_made} of {MAX_TOOL_CALLS} remain."
        )
    ran: dict[str, Any] = {}
    for tool_name, tool_args in calls:
        spec, args = prepare_call(tool_name, tool_args)
        key = _call_signature(tool_name, args.model_dump(mode="json"))
        state.add_activity(
            "tool_request", f"Plan {label}: {tool_name}", plan.plan_id, tool_name=tool_name
        )
        output, duration_ms = await execute_prepared(spec, args, ctx)
        state.tool_calls_made += 1
        item = state.add_evidence(
            category=spec.category,
            source=f"tool:{tool_name}:{output.source}",
            data={"summary": output.summary, "warnings": output.warnings, **output.data}
            if output.error is None
            else {"summary": output.summary, "warnings": output.warnings},
            error=output.error,
            tool_name=tool_name,
            tool_args=args.model_dump(mode="json"),
        )
        state.add_activity(
            "tool_result" if output.error is None else "error",
            f"Plan {label}: {tool_name} {'completed' if output.error is None else 'failed'}",
            output.summary if output.error is None else (output.error or ""),
            tool_name=tool_name, duration_ms=duration_ms, evidence_ids=[item.id],
        )
        ran[key] = (item, output)
    return ran


def _key_for(tool_name: str, tool_args: dict[str, Any]) -> str:
    from ..analysis.loop import _call_signature

    return _call_signature(tool_name, tool_args)


async def capture_baseline(state: Any, plan: ResolutionPlan, settings: Settings) -> ResolutionPlan:
    if plan.baseline_captured_at is not None and (plan.interventions or plan.verifications):
        raise PlanError("Baseline is locked once interventions or verifications exist.")
    use_fixtures = True if state.mode == "simulated" else None
    ran = await _run_criterion_tools(state, plan, settings, use_fixtures, "baseline")
    plan.baseline_evidence_ids = []
    plan.baseline_values = {}
    measurable = 0
    for criterion in plan.criteria:
        item, output = ran[_key_for(criterion.tool_name, criterion.tool_args)]
        if item.id not in plan.baseline_evidence_ids:
            plan.baseline_evidence_ids.append(item.id)
        if output.error is not None:
            plan.baseline_values[criterion.criterion_id] = None
            continue
        observed = resolve_path(output.data, criterion.path)
        if observed is _MISSING:
            plan.baseline_values[criterion.criterion_id] = None
            continue
        measurable += 1
        try:
            import json as _json

            plan.baseline_values[criterion.criterion_id] = _json.loads(
                _json.dumps(observed, default=str)
            )
        except (TypeError, ValueError):
            plan.baseline_values[criterion.criterion_id] = str(observed)
    if measurable == 0:
        raise PlanError(
            "No criterion is measurable: every tool failed or path is absent. "
            "Fix the criteria (tool, args, path) instead of asserting unverifiable claims."
        )
    plan.baseline_captured_at = _now()
    if plan.status == "DRAFT":
        plan.status = "BASELINED"
    state.add_activity(
        "note", f"Plan {plan.plan_id} baselined",
        f"{measurable} of {len(plan.criteria)} criteria measurable pre-fix.",
        evidence_ids=list(plan.baseline_evidence_ids),
    )
    return plan


def record_manual_intervention(state: Any, plan: ResolutionPlan, description: str) -> PlanIntervention:
    if plan.baseline_captured_at is None:
        raise PlanError("Capture the pre-fix baseline before recording an intervention.")
    text = (description or "").strip()
    if not text:
        raise PlanError("A manual intervention needs a description of what was done.")
    record = PlanIntervention(
        kind="manual",
        description=text[:1000],
        recorded_at=_now(),
    )
    plan.interventions.append(record)
    if plan.status == "BASELINED":
        plan.status = "INTERVENED"
    state.add_activity(
        "note", f"Plan {plan.plan_id}: manual intervention recorded",
        text[:500] + " (Claim only: proof requires measured verification.)",
    )
    return record


def link_execution(state: Any, plan: ResolutionPlan, execution_id: str) -> PlanIntervention:
    if plan.baseline_captured_at is None:
        raise PlanError("Capture the pre-fix baseline before linking an execution.")
    execution = next((e for e in state.executions if e.execution_id == execution_id), None)
    if execution is None:
        raise PlanError(f"Unknown execution {execution_id!r} in this investigation.")
    proposal = next((p for p in state.proposals if p.proposal_id == execution.proposal_id), None)
    if plan.remediation_kind == "action":
        if proposal is None or proposal.action_id != plan.action_id or proposal.target != plan.target:
            raise PlanError("Execution does not match the plan's registered action/target.")
    record = PlanIntervention(
        kind="action",
        description=(
            f"Authorized execution {execution.execution_id} "
            f"({proposal.action_id} on {proposal.target}) outcome {execution.outcome}."
            if proposal
            else f"Authorized execution {execution.execution_id}."
        ),
        proposal_id=execution.proposal_id,
        execution_id=execution.execution_id,
        recorded_at=_now(),
    )
    plan.interventions.append(record)
    if plan.status == "BASELINED":
        plan.status = "INTERVENED"
    state.add_activity(
        "note", f"Plan {plan.plan_id}: execution linked",
        record.description,
    )
    return record


async def verify_plan(state: Any, plan: ResolutionPlan, settings: Settings) -> PlanVerification:
    if plan.baseline_captured_at is None:
        raise PlanError("Capture the pre-fix baseline before verification.")
    if not plan.interventions:
        raise PlanError(
            "Verification waits for a recorded intervention: link an authorized "
            "execution or record what was done manually."
        )
    use_fixtures = True if state.mode == "simulated" else None
    ran = await _run_criterion_tools(state, plan, settings, use_fixtures, "verification")
    baseline_items = {item.id: item for item in state.evidence}
    after_ids: list[str] = []
    results: list[CriterionResult] = []
    uncertainties: list[str] = []
    for criterion in plan.criteria:
        key = _key_for(criterion.tool_name, criterion.tool_args)
        item, output = ran[key]
        if item.id not in after_ids:
            after_ids.append(item.id)
        # M007 lineage: the fresh reading supersedes the matching baseline item.
        before_id: str | None = None
        for candidate_id in plan.baseline_evidence_ids:
            candidate = baseline_items.get(candidate_id)
            if (
                candidate is not None
                and candidate.tool_name == criterion.tool_name
                and (candidate.tool_args or {}) == (criterion.tool_args or {})
            ):
                before_id = candidate.id
                break
        if before_id is not None:
            item.refresh_of = before_id
            old = baseline_items[before_id]
            verdict, changes = compare_readings(
                old, None if output.error is not None else item.data, output.error
            )
            state.add_refresh(
                old_evidence_id=before_id,
                new_evidence_id=item.id,
                tool_name=criterion.tool_name,
                verdict=verdict,
                changes=changes,
                old_collected_at=old.collected_at,
                new_collected_at=item.collected_at,
            )
        before_value = plan.baseline_values.get(criterion.criterion_id)
        if output.error is not None:
            results.append(
                CriterionResult(
                    criterion_id=criterion.criterion_id,
                    outcome="inconclusive",
                    observed=None,
                    before_evidence_id=before_id,
                    after_evidence_id=item.id,
                    detail=f"Verification tool failed: {(output.error or '')[:300]}",
                )
            )
            uncertainties.append(
                f"{criterion.description} could not be measured ({criterion.tool_name} failed)."
            )
            continue
        observed = resolve_path(output.data, criterion.path)
        outcome, detail = evaluate(criterion.op, observed, criterion.expected)
        results.append(
            CriterionResult(
                criterion_id=criterion.criterion_id,
                outcome=outcome,  # type: ignore[arg-type]
                observed=None if observed is _MISSING else observed,
                before_evidence_id=before_id,
                after_evidence_id=item.id,
                detail=f"before {before_value!r} -> after "
                f"{(None if observed is _MISSING else observed)!r}; {detail}",
            )
        )
        if outcome == "inconclusive":
            uncertainties.append(f"{criterion.description} could not be graded: {detail}")
    if any(result.outcome == "fail" for result in results):
        outcome_value: str = "NOT_RESOLVED"
    elif any(result.outcome == "inconclusive" for result in results):
        outcome_value = "INCONCLUSIVE"
    else:
        outcome_value = "VERIFIED_RESOLVED"
    if all(iv.kind == "manual" for iv in plan.interventions):
        uncertainties.append(
            "Intervention is technician-reported (manual); the outcome above is "
            "proven only by the fresh measurements cited."
        )
    verification = PlanVerification(
        verification_id=f"ver-{uuid4().hex[:8]}",
        verified_at=_now(),
        after_evidence_ids=after_ids,
        results=results,
        outcome=outcome_value,  # type: ignore[arg-type]
        uncertainties=uncertainties,
    )
    plan.verifications.append(verification)
    plan.status = outcome_value  # type: ignore[assignment]
    if outcome_value == "NOT_RESOLVED":
        failed = [r for r in results if r.outcome == "fail"]
        state.warnings.append(
            f"Plan {plan.plan_id} NOT_RESOLVED: {len(failed)} of {len(results)} "
            "criteria contradicted by fresh measurement."
        )
    elif outcome_value == "INCONCLUSIVE":
        state.warnings.append(
            f"Plan {plan.plan_id} INCONCLUSIVE: missing or failed measurements "
            "prevent verification."
        )
    state.add_activity(
        "note", f"Plan {plan.plan_id} Confirm Fix: {outcome_value}",
        f"{sum(1 for r in results if r.outcome == 'pass')}/{len(results)} criteria pass.",
        evidence_ids=list(after_ids),
    )
    return verification
