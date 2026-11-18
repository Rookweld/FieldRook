"""M033-C: conservative, deterministic ranking of model-proposed diagnostic questions.

This is NOT Shannon information gain, not a diagnosis, and not a substitute
for technician judgment. It ranks at most two *model-authored* questions by
observable proxies: safety, novelty, scope/contrast and falsifiability.
No inference, external request, user-data persistence or generated question
is performed by this module. Previous investigation facts remain authoritative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .guidance import classify_guidance

_WORDS = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOP = frozenset(
    "the and are was were have has had when what which why who how where "
    "you your they their this that these those please can could would "
    "did does do it if then is for not to from on in a an at or with "
    "there here more some any specific information details".split()
)
_CONTRAST = re.compile(
    r"\b(same|different|another|other|versus|vs|only|both|either|"
    r"rather than|compared|without|before|after|instead|"
    r"while|otherwise|across|between|whether)\b",
    re.IGNORECASE,
)
_IMPACT = re.compile(
    r"\b(distinguish|separat\w*|rule out|narrow\w*|isolate|"
    r"favour|favor|support|contradict|change|eliminate|compare|"
    r"indicat\w*|if .{3,100} (then|otherwise)|"
    r"depending on|versus)\b",
    re.IGNORECASE,
)
_VAGUE = re.compile(
    r"\b(more details|more information|provide details|"
    r"give details|tell me more|elaborate|what else|"
    r"what is the issue|what is the problem)\b",
    re.IGNORECASE,
)
_AMBIGUOUS_BOUNDARY = re.compile(
    r"\b(?:at what point|where)\b.{0,80}"
    r"\b(?:error|failure|issue|disconnect|disconnection)\b.{0,60}"
    r"\b(?:stop|stops|stopped)\b",
    re.IGNORECASE,
)
_TIMING_ASK = re.compile(
    r"\bwhen\b.{0,55}\b(start|begin|began|occur|happen)\b",
    re.IGNORECASE,
)
_TIMING_KNOWN = re.compile(
    r"\b(began|started|since|yesterday|today|this morning|last night|last week)\b",
    re.IGNORECASE,
)
_CHECK_ACTION = re.compile(
    r"\b(check|inspect|compare|verify|read|view|test|try|open|start|launch|observe|"
    r"reproduce|look at|confirm)\b", re.IGNORECASE,
)
_CHECK_COMPARISON = re.compile(
    r"\b(without|with|both|different|another|other|only|instead|"
    r"before|after|through|via|under|versus|vs|in .{0,18}mode)\b",
    re.IGNORECASE,
)
_ERROR_ASK = re.compile(r"\b(what|which|provide|give|specify|tell)\b.{0,55}\b(error (?:code|number|message)|exact code)\b", re.IGNORECASE)
_CODE_RE = re.compile(r"\b0x[0-9a-f]{4,}\b", re.IGNORECASE)
_QUESTION = re.compile(r"\?|^\s*(ask|check whether|find out|confirm whether)\b", re.IGNORECASE)


@dataclass(frozen=True)
class QuestionScore:
    score: int
    eligible: bool
    signals: tuple[str, ...]


@dataclass(frozen=True)
class QuestionDecision:
    selected: str | None  # "primary", "alternative", or None (unsafe candidates)
    primary: QuestionScore
    alternative: QuestionScore | None
    explanation: str
    check: QuestionScore | None = None


def _terms(value: str) -> set[str]:
    return {
        word for word in _WORDS.findall(value.lower())
        if word not in _STOP and len(word) >= 3
    }


def _conflicting_reported_code(text: str, problem: str) -> bool:
    """A model may not silently replace an explicitly reported hex error code.

    Only compare to a report containing a recognizable 0x... code. Unknown
    codes are not treated as proof of a value; new observations are handled
    separately in the investigation state.
    """
    known = {value.lower() for value in _CODE_RE.findall(problem)}
    mentioned = {value.lower() for value in _CODE_RE.findall(text)}
    return bool(known and mentioned - known)


def _near_repeat(text: str, asked: list[str]) -> bool:
    a = _terms(text)
    if not a:
        return True
    for previous in asked:
        if text.strip().casefold() == previous.strip().casefold():
            return True
        b = _terms(previous)
        if b and min(len(a), len(b)) >= 3 and len(a & b) / min(len(a), len(b)) >= 0.8:
            return True
    return False


def score_question(
    question: str,
    why: str,
    *,
    problem: str = "",
    hypotheses: list[str] | None = None,
    asked: list[str] | None = None,
    target: str = "remote",
) -> QuestionScore:
    """A bounded heuristic proxy. A high score NEVER verifies actual quality."""
    text = question.strip()[:500]
    if len(text) < 12 or not _QUESTION.search(text):
        return QuestionScore(0, False, ("not-a-usable-question",))
    impact = classify_guidance(text, problem=problem, target=target).impact
    if impact not in ("READ_ONLY", "MANUAL_INFORMATION"):
        return QuestionScore(0, False, (f"non-read-only:{impact}",))
    if _conflicting_reported_code(text, problem):
        return QuestionScore(0, False, ("conflicting-reported-error-code",))

    points = 2
    signals: list[str] = ["safe-question"]
    words = _terms(text)
    if len(words) >= 5:
        points += 1
        signals.append("specific")
    if _CONTRAST.search(text):
        points += 2
        signals.append("tests-a-contrast")
    if _IMPACT.search(why):
        points += 2
        signals.append("stated-decision-impact")
    # Require distinct *hypotheses*, not just several words from one.
    covered = sum(
        bool(words & _terms(title))
        for title in (hypotheses or [])[:8]
        if _terms(title)
    )
    if covered >= 2:
        points += 2
        signals.append("two-hypotheses-linked")
    elif covered == 1:
        points += 1
        signals.append("one-hypothesis-linked")
    if _VAGUE.search(text):
        points -= 4
        signals.append("vague-question")
    if _AMBIGUOUS_BOUNDARY.search(text):
        points -= 4
        signals.append("ambiguous-failure-boundary")
    if _ERROR_ASK.search(text) and _CODE_RE.search(problem):
        points -= 4
        signals.append("asks-known-error-code")
    if _TIMING_ASK.search(text) and _TIMING_KNOWN.search(problem):
        points -= 4
        signals.append("asks-known-onset")
    if _near_repeat(text, asked or []):
        points -= 6
        signals.append("duplicates-prior-question")
    if len(text) > 220 or text.count("?") > 1:
        points -= 2
        signals.append("long-or-multiple-questions")
    return QuestionScore(max(0, min(10, points)), True, tuple(signals))


def choose_question(
    primary: str,
    primary_why: str,
    alternative: str,
    alternative_why: str,
    *,
    problem: str = "",
    hypotheses: list[str] | None = None,
    asked: list[str] | None = None,
    target: str = "remote",
    improvement_margin: int = 2,
) -> QuestionDecision:
    """Prefer a clearly stronger safe alternative; otherwise preserve primary.

    Rewrites are based ONLY on model-provided candidates. Keep decisions
    conservative, transparent and deterministic; ties preserve original.
    """
    main = score_question(
        primary, primary_why, problem=problem, hypotheses=hypotheses,
        asked=asked, target=target,
    )
    alt = (
        score_question(
            alternative, alternative_why, problem=problem,
            hypotheses=hypotheses, asked=asked, target=target,
        )
        if alternative.strip() else None
    )
    if main.eligible and (
        alt is None or not alt.eligible or alt.score < main.score + improvement_margin
    ):
        return QuestionDecision("primary", main, alt, "Primary model question retained.")
    if alt is not None and alt.eligible:
        return QuestionDecision(
            "alternative", main, alt,
            "Selected a safer, more discriminating model-proposed alternative.",
        )
    if main.eligible:
        return QuestionDecision("primary", main, alt, "Primary model question retained.")
    return QuestionDecision(
        None, main, alt, "No safe model-proposed question was available."
    )


def review_task_question(
    task: str,
    payload: dict[str, object] | None,
    *,
    problem: str,
    hypotheses: list[str],
    asked: list[str],
    target: str,
) -> tuple[dict[str, object] | None, QuestionDecision | None]:
    """Conservatively refine one triage or follow-up question without new AI calls.

    Model-proposed alternatives may outrank a weaker original. Never invent
    a question or silently convert a read-only check into a question.
    """
    if payload is None or task not in ("triage", "reassess"):
        return payload, None
    original = dict(payload)
    key = "question" if task == "triage" else "next_step"
    main = original.get(key)
    if not isinstance(main, str):
        main = ""
    if task == "reassess" and main and not _QUESTION.search(main):
        # A concrete read-only technician check is already a valid move;
        # do not replace it with an unrelated question based on scores.
        return original, None
    alternate = original.get("alternative_question")
    if not isinstance(alternate, str):
        alternate = ""
    main_why = original.get("why") if task == "triage" else original.get("verdict")
    alt_why = original.get("alternative_why")
    decision = choose_question(
        main, str(main_why or ""), alternate, str(alt_why or ""),
        problem=problem, hypotheses=hypotheses, asked=asked, target=target,
    )
    if decision.selected == "alternative":
        original[key] = alternate.strip()[:500]
        if task == "triage":
            original["why"] = str(alt_why or "").strip()[:500]
    elif decision.selected is None:
        original[key] = ""
        if task == "triage":
            original["why"] = ""
    if task == "triage":
        raw_check = original.get("next_check")
        if isinstance(raw_check, str) and raw_check.strip():
            check = score_technician_check(
                raw_check, problem=problem, hypotheses=hypotheses,
                asked=asked, target=target,
            )
            if not check.eligible and any(
                signal.startswith("non-read-only:") or signal == "conflicting-reported-error-code"
                for signal in check.signals
            ):
                # Suppress known unsafe / fact-conflicting suggestions.
                original["next_check"] = ""
            elif check.eligible:
                selected_question_score = (
                    decision.alternative.score
                    if decision.selected == "alternative" and decision.alternative
                    else decision.primary.score
                )
                if check.score >= max(5, selected_question_score + 2) and selected_question_score <= 4:
                    original["question"] = ""
                    original["why"] = ""
                    decision = QuestionDecision(
                        "check", decision.primary, decision.alternative,
                        "Model-proposed read-only check offers a stronger "
                        "decision split than the available question.",
                        check,
                    )
            if decision.check is None:
                decision = QuestionDecision(
                    decision.selected, decision.primary, decision.alternative,
                    decision.explanation, check,
                )
    return original, decision


def score_technician_check(
    instruction: str,
    *,
    problem: str = "",
    hypotheses: list[str] | None = None,
    asked: list[str] | None = None,
    target: str = "remote",
) -> QuestionScore:
    """Assess a model-proposed *manual* check as an alternative next move.

    The score is a weak, deterministic proxy for comparing reversible
    technician checks with the model's question. It never executes a check.
    """
    text = instruction.strip()[:500]
    if len(text) < 12:
        return QuestionScore(0, False, ("not-a-check",))
    # Safety/fact-integrity always run FIRST. A command that does not look
    # like a read-only check must never escape these stronger guards.
    impact = classify_guidance(text, problem=problem, target=target).impact
    if impact not in ("MANUAL_INFORMATION", "READ_ONLY"):
        return QuestionScore(0, False, (f"non-read-only:{impact}",))
    if _conflicting_reported_code(text, problem):
        return QuestionScore(0, False, ("conflicting-reported-error-code",))
    if not _CHECK_ACTION.search(text):
        return QuestionScore(0, False, ("not-a-check",))
    points = 2
    signals: list[str] = ["safe-manual-check"]
    points += 1
    signals.append("actionable-read-only-check")
    tokens = _terms(text)
    if len(tokens) >= 5:
        points += 1
        signals.append("specific")
    if _CHECK_COMPARISON.search(text):
        points += 2
        signals.append("controlled-comparison")
    covered = sum(bool(tokens & _terms(h)) for h in (hypotheses or []) if _terms(h))
    if covered >= 2:
        points += 2
        signals.append("two-hypotheses-linked")
    elif covered == 1:
        points += 1
        signals.append("one-hypothesis-linked")
    if _near_repeat(text, asked or []):
        points -= 5
        signals.append("duplicates-prior-ask")
    if len(text) > 220:
        points -= 2
        signals.append("overlong-check")
    return QuestionScore(max(0, min(10, points)), True, tuple(signals))
