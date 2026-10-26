"""Independent post-action verification: outcomes from diagnostics, not confidence."""

from __future__ import annotations

import asyncio
from typing import Any

from .registry import ActionSpec


async def run_verification(spec: ActionSpec) -> tuple[str, dict[str, Any], str | None]:
    """Returns (outcome, after_state, error). Never raises."""
    try:
        ok, after = await asyncio.to_thread(spec.verify)
    except Exception as exc:  # noqa: BLE001 - verifier failure is itself an outcome
        return "VERIFICATION_FAILED", {}, f"Verification errored: {exc}"
    if not isinstance(after, dict):
        return "VERIFICATION_FAILED", {}, "Verifier returned malformed state."
    if ok:
        return "VERIFIED_RESOLVED", after, None
    return "VERIFIED_UNRESOLVED", after, None
