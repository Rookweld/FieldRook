"""Corrective-action registry: predefined operations only.

The model may propose a registered action id; it can never define, reshape,
or smuggle an operation. Anything not in REGISTRY cannot execute, period.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from . import demo_worker


class ActionError(RuntimeError):
    pass


class UnknownActionError(ActionError):
    pass


class ActionDisabledError(ActionError):
    pass


class TargetNotAllowedError(ActionError):
    pass


class ArgsValidationError(ActionError):
    pass


class PreconditionError(ActionError):
    pass


class ApprovalError(ActionError):
    pass


class ExecutionError(ActionError):
    pass


class EmptyActionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ActionSpec:
    id: str
    description: str
    targets: frozenset[str]
    args_model: type[BaseModel]
    risk: str  # low | medium | high
    timeout_s: float
    expected_result: str
    verification_method: str
    execute: Callable[[dict[str, Any]], dict[str, Any]]
    verify: Callable[[], tuple[bool, dict[str, Any]]]
    capture_state: Callable[[], dict[str, Any]]
    enabled: bool = True
    failure_modes: tuple[str, ...] = field(default_factory=tuple)


def _recover_demo_worker(args: dict[str, Any]) -> dict[str, Any]:
    del args  # fixed behavior; no parameters
    return demo_worker.recover()


REGISTRY: dict[str, ActionSpec] = {
    "recover_demo_worker": ActionSpec(
        id="recover_demo_worker",
        description=(
            "Restore the application-owned FieldRook demo worker to healthy operation: "
            "reset its control flag to healthy, and restart its own verified process "
            "only when it is not running. Operates solely on demo-worker state files "
            "and its own process; never touches other processes, services, or files."
        ),
        targets=frozenset({"demo-worker"}),
        args_model=EmptyActionArgs,
        risk="low",
        timeout_s=45.0,
        expected_result="Demo worker reports healthy with a fresh heartbeat.",
        verification_method=(
            "Independent health re-read: status must be healthy with a fresh "
            "heartbeat and a verified worker process."
        ),
        execute=_recover_demo_worker,
        verify=demo_worker.verify_healthy,
        capture_state=demo_worker.read_health,
        failure_modes=(
            "worker process fails to start",
            "heartbeat stays stale",
            "worker reports failed after recovery",
            "execution timeout",
        ),
    )
}


def get_action(action_id: object) -> ActionSpec:
    if not isinstance(action_id, str) or action_id not in REGISTRY:
        raise UnknownActionError(f"Unknown action: {action_id!r}.")
    return REGISTRY[action_id]
