"""Policy enforcement for corrective actions: independent backend validation."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from pydantic import ValidationError

from . import demo_worker
from .registry import (
    ActionDisabledError,
    ActionSpec,
    ArgsValidationError,
    PreconditionError,
    TargetNotAllowedError,
    get_action,
)

APPROVAL_TTL_S = 300


def actions_enabled() -> bool:
    return os.environ.get("FIELDROOK_ACTIONS_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def args_hash(args: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def validate_proposal(action_id: object, target: object, args: object) -> tuple[ActionSpec, dict[str, Any]]:
    """Checks 1-4: known, enabled, allowlisted target, schema-valid args."""
    spec = get_action(action_id)
    if not actions_enabled() or not spec.enabled:
        raise ActionDisabledError(f"Action '{spec.id}' is disabled in this environment.")
    if not isinstance(target, str) or target not in spec.targets:
        raise TargetNotAllowedError(f"Target {target!r} is not allowed for '{spec.id}'.")
    if not isinstance(args, dict):
        raise ArgsValidationError("Action arguments must be an object.")
    try:
        validated = spec.args_model.model_validate(args)
    except ValidationError as exc:
        raise ArgsValidationError(f"Invalid arguments for '{spec.id}': {exc}") from exc
    return spec, validated.model_dump(mode="json")


def check_preconditions(spec: ActionSpec, target: str) -> None:
    """Check 5: the problem the action fixes must actually be present."""
    if spec.id == "recover_demo_worker":
        health = demo_worker.read_health()
        if health.get("status") == "healthy":
            raise PreconditionError(
                "Demo worker is already healthy; recovery is not applicable."
            )


def investigation_digest(ev_counter: int, seq_counter: int, summary: str | None) -> str:
    material = json.dumps([ev_counter, seq_counter, summary or ""], sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
