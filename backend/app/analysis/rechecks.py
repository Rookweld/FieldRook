"""Targeted re-check recommendations from investigation state.

Suggestions are deterministic and evidence-linked: failed collections worth
retrying, readings involved in a contradiction, and readings older than the
evidence TTL. Each suggestion names the exact evidence item and tool so the
technician can re-run one focused check instead of restarting. Empty when the
tool budget is exhausted (a re-check the backend would refuse is not useful
guidance).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..schemas import RecheckSuggestion
from .contradictions import detect_contradictions

MAX_SUGGESTIONS = 5


def _age_s(collected_at: Any, now: datetime) -> float:
    if isinstance(collected_at, datetime):
        moment = collected_at
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return (now - moment).total_seconds()
    return 0.0


def suggest_rechecks(state: Any, evidence_ttl_s: float, tool_calls_max: int) -> list[RecheckSuggestion]:
    if state.tool_calls_made >= tool_calls_max:
        return []
    now = datetime.now(timezone.utc)
    contradictions = detect_contradictions(state.problem, list(state.evidence))
    conflicted: set[str] = set()
    for hit in contradictions:
        conflicted.update(hit.evidence_ids)

    ranked: list[tuple[int, RecheckSuggestion]] = []
    for item in state.evidence:
        if not item.tool_name:
            continue  # screenshots and legacy rows cannot be re-run
        if item.id in conflicted:
            ranked.append(
                (
                    0,
                    RecheckSuggestion(
                        evidence_id=item.id,
                        tool_name=item.tool_name,
                        reason=(
                            f"{item.id} ({item.category}) disagrees with another "
                            "observation; a fresh reading shows which one is stale."
                        ),
                    ),
                )
            )
        elif item.error is not None:
            ranked.append(
                (
                    1,
                    RecheckSuggestion(
                        evidence_id=item.id,
                        tool_name=item.tool_name,
                        reason=(
                            f"{item.id} ({item.category}) failed to collect "
                            f"({(item.error or '')[:120]}); retrying may succeed."
                        ),
                    ),
                )
            )
        elif _age_s(item.collected_at, now) > evidence_ttl_s:
            ranked.append(
                (
                    2,
                    RecheckSuggestion(
                        evidence_id=item.id,
                        tool_name=item.tool_name,
                        reason=(
                            f"{item.id} ({item.category}) is older than the "
                            f"{evidence_ttl_s:g}s evidence TTL; system state may have changed."
                        ),
                    ),
                )
            )
    ranked.sort(key=lambda entry: entry[0])
    seen: set[str] = set()
    suggestions: list[RecheckSuggestion] = []
    for _, suggestion in ranked:
        if suggestion.evidence_id in seen:
            continue
        seen.add(suggestion.evidence_id)
        suggestions.append(suggestion)
        if len(suggestions) >= MAX_SUGGESTIONS:
            break
    return suggestions
