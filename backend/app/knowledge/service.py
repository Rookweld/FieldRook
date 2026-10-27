"""Technician's memory: record, match, recheck, and manage knowledge.

Matching is deterministic and inspectable: every surfaced match lists the
signals that fired (identity, event codes, symptoms, category, evidence
values) with integer weights, plus concrete differences. There are no
confidence percentages. A historical resolution is a reference for the
technician, never proof about the current incident.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..analysis.loop import MAX_TOOL_CALLS
from ..config import Settings
from ..resolutions.service import MISSING, evaluate, resolve_path
from ..schemas import (
    KnowledgeEntry,
    KnowledgeLink,
    KnowledgeMatch,
    MatchSignal,
    RegressionCheck,
)
from ..tools.registry import ToolContext, execute_prepared, prepare_call
from . import signatures as sig
from .redact import redact_text

# Inspectable integer weights. A match surfaces at strength >= MIN_STRENGTH,
# so a bare category overlap (+2) alone never matches.
W_IDENTITY = 4
W_EVENT_CODE = 3
W_SYMPTOM = 1
W_SYMPTOM_CAP = 5
W_CATEGORY = 2
W_EVIDENCE = 3
MIN_STRENGTH = 3
MAX_MATCHES = 20


class KnowledgeError(ValueError):
    pass


class KnowledgeBudgetError(KnowledgeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def fingerprint(problem: str, service_name: str | None, evidence: list[Any]) -> dict[str, Any]:
    usable = [item for item in evidence if getattr(item, "error", None) is None]
    symptoms = sig.normalize_symptoms(problem)
    category = sig.classify_category(problem, usable)
    identity = sig.extract_identity(problem, service_name, usable)
    codes = sig.extract_event_codes(evidence)
    return {
        "symptoms": symptoms,
        "category": category,
        "identity": identity,
        "codes": codes,
        "signature": sig.build_signature(evidence),
        "cluster_key": sig.cluster_key(category, symptoms, identity, codes),
    }


def _plan_outcome(state: Any) -> tuple[str, Any | None]:
    verified = [p for p in getattr(state, "plans", []) if p.verifications]
    if not verified:
        return "UNRESOLVED", None
    plan = verified[-1]
    return str(plan.status), plan


def record_entry(
    state: Any, confirmed_cause: str = "", existing: list[KnowledgeEntry] | None = None
) -> tuple[KnowledgeEntry, bool]:
    """Snapshot an investigation as knowledge. Returns (entry, created).

    Repeat recordings with the same cluster, outcome, and intervention merge
    into one entry (occurrence count grows); anything else stays separate so
    verified and failed outcomes are never conflated.
    """
    if not state.evidence:
        raise KnowledgeError("Nothing to remember: the investigation has no evidence.")
    printed = fingerprint(state.problem, state.service_name, list(state.evidence))
    outcome, plan = _plan_outcome(state)
    causes = state.assessment.causes if state.assessment else []
    confirmed = (confirmed_cause or "").strip()
    if confirmed:
        root_cause, cause_verified = confirmed[:500], True
    elif causes:
        root_cause = f"{causes[0].title} (likelihood {causes[0].likelihood}, INFERRED hypothesis)"
        cause_verified = False
    else:
        root_cause, cause_verified = None, False
    intervention, intervention_kind = "", "none"
    criteria: list[Any] = []
    baseline_values: dict[str, Any] = {}
    verified_values: dict[str, Any] = {}
    verified_at = None
    source_plan_id = None
    if plan is not None:
        source_plan_id = plan.plan_id
        intervention_kind = plan.remediation_kind
        if plan.interventions:
            last = plan.interventions[-1]
            intervention = redact_text(last.description)[:500]
        criteria = list(plan.criteria)
        baseline_values = dict(plan.baseline_values)
        if plan.verifications:
            latest = plan.verifications[-1]
            verified_at = latest.verified_at
            for result in latest.results:
                verified_values[result.criterion_id] = result.observed
    link = KnowledgeLink(
        investigation_id=state.id,
        plan_id=source_plan_id,
        outcome=outcome,  # type: ignore[arg-type]
        recorded_at=_now(),
    )
    for entry in existing or []:
        if (
            entry.cluster_key == printed["cluster_key"]
            and entry.outcome == outcome
            and entry.intervention_kind == intervention_kind
            and entry.intervention[:200] == intervention[:200]
        ):
            entry.occurrence_count += 1
            entry.investigations.append(link)
            return entry, False
    entry = KnowledgeEntry(
        entry_id=f"know-{uuid4().hex[:12]}",
        cluster_key=printed["cluster_key"],
        source_investigation_id=state.id,
        source_plan_id=source_plan_id,
        problem=redact_text(state.problem)[:2000],
        category=printed["category"],
        symptoms=printed["symptoms"],
        identity=printed["identity"],
        event_codes=printed["codes"],
        evidence_signature=printed["signature"],
        root_cause=root_cause,
        root_cause_verified=cause_verified,
        intervention=intervention,
        intervention_kind=intervention_kind,
        criteria=criteria,
        baseline_values=baseline_values,
        verified_values=verified_values,
        outcome=outcome,  # type: ignore[arg-type]
        verified_at=verified_at,
        created_at=_now(),
        source_evidence_ids=[item.id for item in state.evidence],
        occurrence_count=1,
        investigations=[link],
    )
    return entry, True


def match_entries(
    problem: str,
    service_name: str | None,
    evidence: list[Any],
    entries: list[KnowledgeEntry],
    limit: int = 5,
) -> list[KnowledgeMatch]:
    current = fingerprint(problem, service_name, evidence)
    current_categories = {
        getattr(item, "category", "") for item in evidence if getattr(item, "error", None) is None
    }
    matches: list[KnowledgeMatch] = []
    for entry in entries:
        signals: list[MatchSignal] = []
        if entry.identity and entry.identity == current["identity"]:
            signals.append(
                MatchSignal(
                    signal="identity",
                    detail=f"Same identity: {entry.identity}.",
                    weight=W_IDENTITY,
                )
            )
        shared_codes = sorted(set(entry.event_codes) & set(current["codes"]))
        for code in shared_codes:
            signals.append(
                MatchSignal(
                    signal="event-code",
                    detail=f"Shared Windows event code {code}.",
                    weight=W_EVENT_CODE,
                )
            )
        shared_symptoms = sorted(set(entry.symptoms) & set(current["symptoms"]))
        for token in shared_symptoms[:W_SYMPTOM_CAP]:
            signals.append(
                MatchSignal(
                    signal="symptom",
                    detail=f"Shared symptom word: {token}.",
                    weight=W_SYMPTOM,
                )
            )
        if entry.category and entry.category == current["category"]:
            signals.append(
                MatchSignal(
                    signal="category",
                    detail=f"Same problem category: {entry.category}.",
                    weight=W_CATEGORY,
                )
            )
        for category, value in sorted(entry.evidence_signature.items()):
            if current["signature"].get(category) == value:
                signals.append(
                    MatchSignal(
                        signal="evidence",
                        detail=f"Same {category} reading: {value}.",
                        weight=W_EVIDENCE,
                    )
                )
        strength = sum(s.weight for s in signals)
        if strength < MIN_STRENGTH:
            continue
        differences: list[str] = []
        if entry.identity and current["identity"] and entry.identity != current["identity"]:
            differences.append(
                f"Identity differs: historical {entry.identity}, current {current['identity']}."
            )
        only_hist = sorted(set(entry.event_codes) - set(current["codes"]))
        only_now = sorted(set(current["codes"]) - set(entry.event_codes))
        if only_hist:
            differences.append(f"Historical-only event codes: {', '.join(only_hist)}.")
        if only_now:
            differences.append(f"Current-only event codes: {', '.join(only_now)}.")
        for category, value in sorted(entry.evidence_signature.items()):
            current_value = current["signature"].get(category)
            if current_value is not None and current_value != value:
                differences.append(
                    f"{category} differs: historical {value}, current {current_value}."
                )
        if entry.category != current["category"]:
            differences.append(
                f"Category differs: historical {entry.category}, current {current['category']}."
            )
        missing = sorted(set(entry.evidence_signature) - current_categories)
        missing_notes = [f"Collect {category} evidence to compare with history." for category in missing]
        matches.append(
            KnowledgeMatch(
                entry=entry,
                strength=strength,
                signals=signals,
                differences=differences,
                missing_evidence=missing_notes,
            )
        )
    matches.sort(key=lambda m: (-m.strength, m.entry.created_at))
    return matches[: max(1, min(limit, MAX_MATCHES))]


async def recheck_entry(
    state: Any, entry: KnowledgeEntry, settings: Settings
) -> RegressionCheck:
    """Re-run a verified entry's criteria against current state.

    The historical entry is never modified: this appends a fresh check to
    the investigation. CONFIRMED means still healthy; REGRESSION means a
    measured criterion now fails; INCONCLUSIVE means tools failed.
    """
    if entry.outcome != "VERIFIED_RESOLVED" or not entry.criteria:
        raise KnowledgeError(
            "Only verified resolutions with stored criteria can be rechecked."
        )
    use_fixtures = True if state.mode == "simulated" else None
    ctx = ToolContext(settings=settings, use_fixtures=use_fixtures)
    seen: dict[str, tuple[str, dict[str, Any]]] = {}
    for criterion in entry.criteria:
        import json as _json

        key = criterion.tool_name + ":" + _json.dumps(
            criterion.tool_args, sort_keys=True, default=str
        )
        seen.setdefault(key, (criterion.tool_name, criterion.tool_args))
    calls = list(seen.values())
    if state.tool_calls_made + len(calls) > MAX_TOOL_CALLS:
        raise KnowledgeBudgetError(
            f"Recheck needs {len(calls)} call(s) but only "
            f"{MAX_TOOL_CALLS - state.tool_calls_made} of {MAX_TOOL_CALLS} remain."
        )
    from ..schemas import CriterionResult

    ran: dict[str, Any] = {}
    evidence_ids: list[str] = []
    for tool_name, tool_args in calls:
        from ..analysis.loop import _call_signature

        spec, args = prepare_call(tool_name, tool_args)
        key = _call_signature(tool_name, args.model_dump(mode="json"))
        state.add_activity(
            "tool_request", f"Knowledge recheck: {tool_name}",
            entry.entry_id, tool_name=tool_name,
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
        evidence_ids.append(item.id)
        state.add_activity(
            "tool_result" if output.error is None else "error",
            f"Knowledge recheck: {tool_name} {'completed' if output.error is None else 'failed'}",
            output.summary if output.error is None else (output.error or ""),
            tool_name=tool_name, duration_ms=duration_ms, evidence_ids=[item.id],
        )
        ran[key] = (item, output)
    from ..analysis.loop import _call_signature as _sig

    results = []
    uncertainties: list[str] = []
    for criterion in entry.criteria:
        key = _sig(criterion.tool_name, criterion.tool_args)
        item, output = ran[key]
        historical = entry.verified_values.get(criterion.criterion_id)
        if output.error is not None:
            results.append(
                CriterionResult(
                    criterion_id=criterion.criterion_id,
                    outcome="inconclusive",
                    observed=None,
                    after_evidence_id=item.id,
                    detail=f"Recheck tool failed: {(output.error or '')[:300]}",
                )
            )
            uncertainties.append(f"{criterion.description} could not be re-measured.")
            continue
        observed = resolve_path(output.data, criterion.path)
        outcome, detail = evaluate(criterion.op, observed, criterion.expected)
        shown = None if observed is MISSING else observed
        results.append(
            CriterionResult(
                criterion_id=criterion.criterion_id,
                outcome=outcome,  # type: ignore[arg-type]
                observed=shown,
                after_evidence_id=item.id,
                detail=f"verified {historical!r} -> now {shown!r}; {detail}",
            )
        )
        if outcome == "inconclusive":
            uncertainties.append(f"{criterion.description} could not be graded: {detail}")
    if any(r.outcome == "fail" for r in results):
        outcome_value = "REGRESSION"
    elif any(r.outcome == "inconclusive" for r in results):
        outcome_value = "INCONCLUSIVE"
    else:
        outcome_value = "CONFIRMED"
    check = RegressionCheck(
        check_id=f"reg-{uuid4().hex[:8]}",
        entry_id=entry.entry_id,
        investigation_id=state.id,
        checked_at=_now(),
        outcome=outcome_value,  # type: ignore[arg-type]
        results=results,
        uncertainties=uncertainties,
        evidence_ids=evidence_ids,
    )
    state.regression_checks.append(check)
    if outcome_value == "REGRESSION":
        state.warnings.append(
            f"Possible regression: {entry.entry_id} verified {entry.verified_at}, "
            "but fresh measurements contradict its criteria. Original outcome preserved."
        )
    state.add_activity(
        "note", f"Knowledge recheck {entry.entry_id}: {outcome_value}",
        f"{sum(1 for r in results if r.outcome == 'pass')}/{len(results)} criteria still hold.",
        evidence_ids=list(evidence_ids),
    )
    return check
