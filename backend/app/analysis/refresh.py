"""Historical-vs-current evidence comparison for on-demand reverification.

Comparisons are deterministic and conservative: volatile readings (query
times, heartbeat ages, uptimes, memory samples) are excluded so a rerun is
only reported `changed` when substantive observations differ. Summaries and
warning lists are presentation, not observations, and are excluded too.
"""

from __future__ import annotations

import json
from typing import Any

from ..schemas import EvidenceItem, RefreshVerdict

MAX_CHANGES = 10

# Keys whose values legitimately vary between identical back-to-back runs.
VOLATILE_KEYS = frozenset(
    {
        "summary",
        "warnings",
        "query_ms",
        "heartbeat_age_s",
        "uptime_s",
        "memory_mb",
        "collected_at",
        "timestamp",
        "started",
    }
)


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _stable(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _flatten(value: Any, prefix: str, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        if not value:
            out[prefix or "(root)"] = "{}"
            return
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            _flatten(item, path, out)
    elif isinstance(value, list):
        if not value:
            out[prefix or "(root)"] = "[]"
            return
        if len(value) > 25:
            out[prefix or "(root)"] = f"[list of {len(value)}]"
            return
        for index, item in enumerate(value):
            _flatten(item, f"{prefix}[{index}]", out)
    else:
        text = json.dumps(value, default=str)
        out[prefix or "(root)"] = text if len(text) <= 160 else text[:157] + "..."


def describe_changes(old_data: dict[str, Any], new_data: dict[str, Any]) -> list[str]:
    """Human-readable substantive differences between two readings."""
    old_flat: dict[str, str] = {}
    new_flat: dict[str, str] = {}
    _flatten(_stable(old_data), "", old_flat)
    _flatten(_stable(new_data), "", new_flat)
    differing = sorted(
        path
        for path in set(old_flat) | set(new_flat)
        if old_flat.get(path) != new_flat.get(path)
    )
    changes: list[str] = []
    for path in differing[:MAX_CHANGES]:
        before = old_flat.get(path)
        after = new_flat.get(path)
        if before is None:
            changes.append(f"{path}: (absent) -> {after}")
        elif after is None:
            changes.append(f"{path}: {before} -> (absent)")
        else:
            changes.append(f"{path}: {before} -> {after}")
    if len(differing) > MAX_CHANGES:
        changes.append(f"... and {len(differing) - MAX_CHANGES} more difference(s).")
    return changes


def compare_readings(
    old: EvidenceItem,
    new_data: dict[str, Any] | None,
    new_error: str | None,
) -> tuple[RefreshVerdict, list[str]]:
    """Verdict for a rerun against its historical item.

    - `unavailable`: the rerun failed to collect (historical item kept).
    - `unchanged`: substantive observations match (old error vs new error
      with the same message also counts as unchanged).
    - `changed`: anything substantive differs, including error-to-data or
      data-to-error transitions.
    """
    if new_error is not None:
        if old.error is not None and old.error == new_error:
            return "unchanged", []
        return "unavailable", [
            f"Re-check failed to collect: {new_error[:300]} "
            f"(historical reading kept as {old.id})."
        ]
    assert new_data is not None
    if old.error is not None:
        return "changed", [
            f"Historical reading was an error ({old.error[:200]}); "
            "the re-check collected data."
        ]
    changes = describe_changes(old.data, new_data)
    if not changes:
        return "unchanged", []
    return "changed", changes
