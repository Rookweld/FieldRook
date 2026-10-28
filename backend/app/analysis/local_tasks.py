"""M017 local task pipeline: small prompts, tight caps, honest assembly.

A local CPU model must not be asked for the full Muse Spark assessment in
one giant call (measured: >280s, unusable). Instead the local path runs
small task calls — triage, plan, reassess on follow-ups — each with a
compact prompt, a strict token cap, and its own timeout. M019 routes them
single-decision: one task per round normally (triage OR reassess), with
plan only as recovery when nothing else gives direction. The returned
parts are validated and assembled here into one AnalysisResult; every part
records whether it is model reasoning or deterministic fill so the UI can
label it honestly.

The benchmark harness (eval/local_bench.py) exercises these exact prompts,
so published numbers describe production behavior.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Next steps phrased as requests for information route to questions.
_ASK_RE = re.compile(r"^\s*(ask|find out|check with|confirm with)\b", re.IGNORECASE)

TASK_LIMITS: dict[str, dict[str, int]] = {
    # task -> output cap (tokens) + call timeout (seconds)
    "triage": {"num_predict": 220, "timeout": 120},
    "plan": {"num_predict": 380, "timeout": 180},
    "reassess": {"num_predict": 220, "timeout": 120},
    "synthesize": {"num_predict": 900, "timeout": 300},  # bench reference only
    "vision": {"num_predict": 300, "timeout": 240},
}

TASK_REQUIRED_KEYS: dict[str, list[str]] = {
    "triage": ["question", "why", "hypotheses", "next_check", "unknowns"],
    "plan": ["steps"],
    "reassess": ["verdict", "weakened", "next_step"],
    "synthesize": ["summary", "understanding", "causes", "uncertainties"],
    "vision": ["app", "dialog_title", "error_text", "error_code"],
}


VISION_PROMPT = (
    "Describe the attached Windows error dialog. Reply with ONLY this JSON "
    "object, no other text: {\"app\": \"<application name or null>\", "
    "\"dialog_title\": \"<window title or null>\", \"error_text\": \"<exact error "
    "message or null>\", \"error_code\": \"<code like 0x... or null>\"}. Use null "
    "for anything unreadable; never invent text."
)


def triage_prompt(problem: str, evidence_digest: str, target: str) -> str:
    evidence = evidence_digest.strip() or "No diagnostic evidence collected yet."
    scope = (
        "The affected machine is a different computer: host measurements do not "
        "apply, so reason only from the report and propose technician checks."
        if target != "local"
        else "Reason from the report and evidence below."
    )
    return (
        "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
        "this JSON object, no other text: {\"question\": \"<one clarifying question>\", "
        "\"why\": \"<why the answer changes the diagnosis>\", \"hypotheses\": "
        "[{\"title\": \"<possible cause>\", \"why\": \"<one line>\"}], \"next_check\": "
        "\"<one safe read-only check>\", \"unknowns\": [\"<what is still unknown>\"]}. "
        "At most 2 hypotheses and 2 unknowns. The question must name something "
        "concrete (a symptom, timing, scope, or error text); never ask for "
        "\"more details\" in general. Ask the question whose answer most "
        "narrows the cause, in this order: scope (one or many? which machine? "
        "which users?), timing (when did it start? what changed?), exact "
        "symptoms. Never ask for readings already present in Evidence, and "
        "avoid version-number or have-you-rebooted openers unless the report "
        "points there. Ask only what the technician must answer; anything a "
        "safe read-only check could settle belongs in next_check instead. "
        f"{scope} Problem: {problem.strip()[:800]} Evidence: {evidence[:1500]}"
    )


def plan_prompt(problem: str, context: str, target: str) -> str:
    scope = (
        "The affected machine is a different computer: use only TECHNICIAN_CHECK, "
        "CLARIFYING_QUESTION, or EXTERNAL_SYSTEM_CHECK kinds."
        if target != "local"
        else "Use TECHNICIAN_CHECK, CLARIFYING_QUESTION, or EXTERNAL_SYSTEM_CHECK kinds."
    )
    return (
        "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
        "this JSON object, no other text: {\"steps\": [{\"instruction\": \"<what to do>\", "
        "\"why\": \"<why it matters>\", \"kind\": \"<step kind>\", \"expect\": \"<what "
        "different results would mean>\"}]}. At most 4 steps, ordered by usefulness. "
        f"{scope} Problem: {problem.strip()[:800]} Context: {context.strip()[:1200]}"
    )


def reassess_prompt(
    hypothesis_titles: list[str],
    observation: str,
    asked_questions: list[str] | None = None,
    thin_streak: int = 0,
) -> str:
    titles = "; ".join(t for t in hypothesis_titles if t)[:600] or "none tracked yet"
    asked = "; ".join(q[:80] for q in (asked_questions or []) if q)[:400]
    no_repeat = (
        f" Already-asked questions (do not repeat or paraphrase): [{asked}]."
        if asked
        else ""
    )
    return (
        "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
        "this JSON object, no other text: {\"verdict\": \"<one sentence: what the new "
        "observation means>\", \"weakened\": [\"<hypothesis titles now less likely>\"], "
        "\"next_step\": \"<the single most useful next check or question>\"}. "
        "When the observation contradicts the open hypotheses or answers "
        "nothing, prefer a question whose answer would discriminate the new "
        "possibilities over another check. Never ask about a hypothesis this "
        "observation just ruled out; pursue the surviving alternatives. "
        + (
            f"Note: the last {thin_streak} technician answers gave no usable "
            "information. Switch to a different branch or propose a concrete "
            "check the technician CAN perform instead of re-asking. "
            if thin_streak >= 2
            else ""
        )
        + f"Open hypotheses: [{titles}]. New technician observation: {observation.strip()[:800]}"
        f"{no_repeat}"
    )


def synthesize_prompt(problem: str, evidence_digest: str, target: str) -> str:
    """Full-assessment prompt. Bench reference only: production assembles."""
    evidence = evidence_digest.strip() or "No diagnostic evidence collected yet."
    return (
        "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
        "this JSON object, no other text: {\"summary\": \"<2 sentences>\", "
        "\"understanding\": \"<reported vs observed>\", \"causes\": [{\"title\": ..., "
        "\"description\": ..., \"likelihood\": \"<high|medium|low>\"}], "
        "\"uncertainties\": [...], \"missing_evidence\": [...], "
        "\"questions\": [{\"question\": ..., \"why\": ...}]}. "
        f"Problem: {problem.strip()[:800]} Target: {target}. Evidence: {evidence[:1500]}"
    )


def evidence_digest(items: list[dict[str, Any]], limit: int = 12) -> str:
    """Compact one-line-per-item evidence summary for task prompts."""
    lines: list[str] = []
    for item in items[:limit]:
        if item.get("error"):
            lines.append(f"{item.get('id')}: {item.get('category')} FAILED ({item.get('error')})")
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        keys = ",".join(sorted(data.keys())[:6])
        lines.append(
            f"{item.get('id')}: {item.get('category')} via {item.get('tool_name') or item.get('source')} [{keys}]"
        )
    if len(items) > limit:
        lines.append(f"(+{len(items) - limit} more)")
    return "\n".join(lines)


def extract_json(text: str) -> dict[str, Any] | None:
    """First balanced top-level {...} span parsed as JSON, else None."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except ValueError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def missing_keys(payload: dict[str, Any], task: str) -> list[str]:
    return [key for key in TASK_REQUIRED_KEYS.get(task, []) if key not in payload]


def _short(text: str, limit: int) -> str:
    return " ".join((text or "").split())[:limit]


def assemble_assessment(
    problem: str,
    evidence: list[Any],
    triage: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    reassess: dict[str, Any] | None,
    model_label: str,
    target: str,
    plan_skipped: bool = False,
) -> tuple[Any, list[str], list[str]]:
    """Build one AnalysisResult from validated task parts.

    Returns (AnalysisResult, warnings, model_parts): model_parts names which
    sections came from the model (triage/plan/reassess) so callers can label
    the deterministic remainder honestly.
    """
    from ..schemas import (
        AnalysisResult,
        ObservedFact,
        RootCause,
        RunbookStep,
        SuggestedHypothesis,
        SuggestedPlan,
        SuggestedPlanStep,
        SuggestedQuestion,
    )

    usable = [item for item in evidence if getattr(item, "error", None) is None]
    failed = [item for item in evidence if getattr(item, "error", None) is not None]
    warnings: list[str] = []
    model_parts: list[str] = []

    facts = [
        ObservedFact(
            statement=(
                f"{item.category} reading {item.id} collected via "
                f"{item.tool_name or item.source}."
            ),
            evidence_ids=[item.id],
        )
        for item in usable[:12]
    ]

    causes: list[RootCause] = []
    suggested_hypotheses: list[SuggestedHypothesis] = []
    suggested_questions: list[SuggestedQuestion] = []
    next_steps: list[RunbookStep] = []
    next_actions: list[str] = []
    suggested_steps: list[SuggestedPlanStep] = []
    understanding_bits: list[str] = [
        f"Reported: {_short(problem, 200)}",
        f"Observed: {len(usable)} usable evidence item(s).",
    ]
    uncertainties: list[str] = [
        f"Local {model_label} reasoning on this computer; hypotheses are unverified."
    ]
    for item in failed[:4]:
        uncertainties.append(f"{item.id} ({item.category}) failed: {item.error}")

    if triage:
        model_parts.append("triage")
        for entry in (triage.get("hypotheses") or [])[:2]:
            if not isinstance(entry, dict) or not str(entry.get("title", "")).strip():
                continue
            title = _short(str(entry.get("title")), 200)
            why = _short(str(entry.get("why", "")), 500)
            causes.append(
                RootCause(
                    title=title,
                    description=why or "Suggested by local triage; no supporting measurements yet.",
                    likelihood="low",
                    evidence_ids=[],
                )
            )
            suggested_hypotheses.append(
                SuggestedHypothesis(title=title, description=why, status="active")
            )
        question = _short(str(triage.get("question", "")), 500)
        why = _short(str(triage.get("why", "")), 500)
        if question:
            suggested_questions.append(SuggestedQuestion(question=question, why=why))
        for unknown in (triage.get("unknowns") or [])[:2]:
            if str(unknown).strip():
                uncertainties.append(_short(str(unknown), 300))
        next_check = _short(str(triage.get("next_check", "")), 300)
    else:
        next_check = ""
        if reassess is None:
            # Initial round with no triage: say so plainly. Follow-up rounds
            # skip triage by design and keep their tracked hypotheses.
            warnings.append("Triage produced no usable output; hypotheses come from deterministic fallback.")
            causes.append(
                RootCause(
                    # Technician-meaningful: cause titles surface as hypotheses
                    # (M018: the internal note leaked into the hypothesis list).
                    title="No verified cause: affected-machine observations are missing",
                    description="No usable assessment yet. Supply screenshots, error "
                    "codes, or manual test results to open testable hypotheses.",
                    likelihood="low",
                    evidence_ids=[],
                )
            )

    if reassess:
        model_parts.append("reassess")
        verdict = _short(str(reassess.get("verdict", "")), 500)
        if verdict:
            understanding_bits.append(f"Reassessment: {verdict}")
        for title in (reassess.get("weakened") or [])[:4]:
            if str(title).strip():
                suggested_hypotheses.append(
                    SuggestedHypothesis(title=_short(str(title), 200), status="weakened")
                )
        next_step = _short(str(reassess.get("next_step", "")), 500)
        if next_step:
            # M019 single-decision routing: a next step phrased as a question
            # becomes an open question, otherwise a technician check step —
            # no second model call needed to structure it. Ask-prefixed
            # instructions ("Ask the technician to ...") are questions
            # semantically, so they route to questions verbatim.
            if next_step.rstrip().endswith("?") or _ASK_RE.match(next_step):
                suggested_questions.append(
                    SuggestedQuestion(question=next_step, why="Reassessment follow-up.")
                )
            else:
                suggested_steps.append(
                    SuggestedPlanStep(
                        instruction=next_step,
                        why="Reassessment follow-up.",
                        kind="TECHNICIAN_CHECK",  # type: ignore[arg-type]
                    )
                )

    if plan:
        model_parts.append("plan")
        for entry in (plan.get("steps") or [])[:4]:
            if not isinstance(entry, dict) or not str(entry.get("instruction", "")).strip():
                continue
            instruction = _short(str(entry.get("instruction")), 500)
            why = _short(str(entry.get("why", "")), 500)
            raw_kind = str(entry.get("kind", "TECHNICIAN_CHECK")).strip().upper()
            if raw_kind not in ("TECHNICIAN_CHECK", "CLARIFYING_QUESTION", "EXTERNAL_SYSTEM_CHECK"):
                warnings.append(
                    f"Plan step {len(suggested_steps) + 1} used unknown kind "
                    f"{raw_kind[:40]!r}; treated as TECHNICIAN_CHECK."
                )
                kind = "TECHNICIAN_CHECK"
            else:
                kind = raw_kind
            expect = _short(str(entry.get("expect", "")), 500)
            next_actions.append(instruction)
            next_steps.append(
                RunbookStep(
                    step=instruction,
                    why=why or "Suggested by the local plan.",
                    inspect=expect or "The reported outcome.",
                    confirms="A reported outcome corroborates one hypothesis over the others.",
                    impact="read-only" if kind != "EXTERNAL_SYSTEM_CHECK" else "unknown",
                )
            )
            suggested_steps.append(
                SuggestedPlanStep(
                    instruction=instruction,
                    why=why,
                    kind=kind,  # type: ignore[arg-type]
                    expected_observations=[expect] if expect else [],
                )
            )
    elif plan_skipped and next_check:
        # M019 single-decision: plan was deliberately not requested; the
        # triage check becomes the one current step without a second call.
        next_actions.append(next_check)
        next_steps.append(
            RunbookStep(
                step=next_check,
                why="Single next check from triage.",
                inspect="The reported outcome.",
                confirms="A reported outcome corroborates one hypothesis over the others.",
                impact="read-only",
            )
        )
        suggested_steps.append(
            SuggestedPlanStep(
                instruction=next_check,
                why="Single next check from triage.",
                kind="TECHNICIAN_CHECK",  # type: ignore[arg-type]
            )
        )
    elif not plan_skipped:
        warnings.append("Plan generation produced no usable output; the deterministic planner fills in.")
    if next_check and not next_actions:
        next_actions.append(next_check)

    from .guidance import classify_guidance

    for runbook in next_steps:
        rb_verdict = classify_guidance(
            runbook.step, runbook.why or "", problem=problem, target=target
        )
        runbook.guidance_impact = rb_verdict.impact
        runbook.safety_note = rb_verdict.safety_note[:1000]

    missing = [q.question for q in suggested_questions]
    if not missing and reassess is None:
        # Technician-meaningful fallback asks. These render as questions and
        # plan steps when the model says nothing usable, so they must never
        # be internal notes (M018: placeholder text leaked to technicians).
        missing = [
            "Which computer is affected (this host or another machine).",
            "Exact error text or code from the affected computer.",
        ]
    summary = (
        f"Local {model_label} triage of '{_short(problem, 100)}': "
        f"{len(causes)} tentative cause(s), {len(suggested_questions)} open question(s). "
        "Causes below are unverified hypotheses."
    )
    return (
        AnalysisResult(
            summary=summary,
            facts=facts,
            causes=causes,
            uncertainties=uncertainties,
            missing_evidence=missing,
            next_actions=next_actions,
            next_steps=next_steps,
            explanation=(
                f"FieldRook ran bounded local reasoning ({model_label}) over {len(usable)} "
                f"evidence items: {', '.join(model_parts) or 'no model parts; deterministic only'}. "
                "OBSERVED facts restate collected readings. INFERRED causes are local-model "
                "suggestions without measured support. No corrective action was taken."
            ),
            mode="live",
            model=model_label,
            provider="local",
            understanding=" ".join(understanding_bits)[:2000],
            suggested_hypotheses=suggested_hypotheses,
            suggested_plan=SuggestedPlan(steps=suggested_steps) if suggested_steps else None,
            suggested_questions=suggested_questions,
        ),
        warnings,
        model_parts,
    )
