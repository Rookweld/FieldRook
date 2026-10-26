"""Controlled execution: validated approvals in, verified outcomes out.

Exactly one execution per proposal may run at a time; concurrent attempts are
rejected. Before/after states are captured as evidence. The outcome always
comes from independent verification, never from the executor or the model.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..schemas import ActionExecution
from . import audit
from .approval import consume_approval
from .registry import get_action
from .verification import run_verification

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def _lock_for(proposal_id: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(proposal_id)
        if lock is None:
            lock = threading.Lock()
            _locks[proposal_id] = lock
        return lock


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def execute_approved(
    state: Any, proposal_id: str, token: str, args: object
) -> ActionExecution:
    lock = _lock_for(f"{state.id}:{proposal_id}")
    if not lock.acquire(blocking=False):
        from .registry import ApprovalError

        raise ApprovalError("Execution already in progress for this proposal.")
    try:
        return await _execute_inner(state, proposal_id, token, args)
    finally:
        lock.release()


async def _execute_inner(
    state: Any, proposal_id: str, token: str, args: object
) -> ActionExecution:
    consume_approval(state, proposal_id, token, args)  # APPROVED -> EXECUTING or raise
    proposal = next(p for p in state.proposals if p.proposal_id == proposal_id)
    spec = get_action(proposal.action_id)
    execution = ActionExecution(
        execution_id=f"exe-{uuid4().hex[:12]}",
        proposal_id=proposal_id,
        started_at=_now(),
    )
    state.executions.append(execution)
    audit.record_execution_started(state, proposal)
    try:
        execution.before_state = await asyncio.to_thread(spec.capture_state)
    except Exception as exc:  # noqa: BLE001 - before-state is best effort
        execution.before_state = {"error": f"before-state capture failed: {exc}"}
    before_item = state.add_evidence(
        category="action_before",
        source=f"action:{spec.id}:live",
        data={"action_id": spec.id, "target": proposal.target, "state": execution.before_state},
    )
    outcome = "EXECUTION_FAILED"
    error: str | None = None
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(spec.execute, dict(proposal.args)),
            timeout=spec.timeout_s,
        )
        execution.after_state = result.get("after", {}) if isinstance(result, dict) else {}
        outcome = "EXECUTED_UNVERIFIED"
    except asyncio.TimeoutError:
        error = f"Execution exceeded the {spec.timeout_s:g}s timeout."
    except Exception as exc:  # noqa: BLE001 - action failure is an outcome
        error = f"Execution failed: {exc}"
    if outcome == "EXECUTED_UNVERIFIED":
        audit.record_verification_started(state, proposal)
        outcome, after_state, verify_error = await run_verification(spec)
        execution.after_state = after_state
        error = verify_error
    else:
        try:
            execution.after_state = await asyncio.to_thread(spec.capture_state)
        except Exception:  # noqa: BLE001 - best effort on failure paths
            pass
    execution.outcome = outcome
    execution.error = error
    execution.finished_at = _now()
    proposal.status = outcome  # type: ignore[assignment]
    after_item = state.add_evidence(
        category="action_after",
        source=f"action:{spec.id}:live",
        data={"action_id": spec.id, "target": proposal.target, "state": execution.after_state},
    )
    audit.record_execution_finished(
        state,
        proposal,
        outcome,
        error or spec.expected_result,
        [before_item.id, after_item.id],
    )
    return execution
