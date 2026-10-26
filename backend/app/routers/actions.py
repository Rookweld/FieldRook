"""Corrective-action endpoints: propose, approve, reject, execute.

Approval is never inferred: only explicit calls to these endpoints count, and
only from the local application (cross-origin browser requests are rejected).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..actions.approval import approve, consume_approval, create_proposal, reject
from ..actions.executor import execute_approved
from ..actions.registry import ActionError
from ..investigations.store import store
from ..schemas import InvestigationResponse

router = APIRouter(tags=["actions"])

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}


def require_local_origin(request: Request) -> None:
    """Reject browser-driven cross-origin calls; allow direct local clients."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    try:
        host = (urlparse(origin).hostname or "").lower()
    except ValueError:
        raise HTTPException(status_code=403, detail="Refused: unparseable origin.")
    if host not in LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Refused: cross-origin request.")


class ProposeRequest(BaseModel):
    action_id: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=1000)


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class ExecuteRequest(BaseModel):
    approval_token: str = Field(min_length=1, max_length=128)
    args: dict[str, Any] = Field(default_factory=dict)


class ApprovalResponse(BaseModel):
    investigation: InvestigationResponse
    approval_token: str
    expires_in_s: int


class ExecuteResponse(BaseModel):
    investigation: InvestigationResponse
    execution_id: str
    outcome: str


def _uses_fixtures(state: Any) -> bool:
    return state.mode == "simulated"


@router.post(
    "/api/investigations/{investigation_id}/proposals",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
def propose_action(investigation_id: str, request: ProposeRequest) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    try:
        create_proposal(state, request.action_id, request.target, request.args, request.reason, [])
    except ActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/proposals/{proposal_id}/approve",
    response_model=ApprovalResponse,
    dependencies=[Depends(require_local_origin)],
)
def approve_proposal(proposal_id: str) -> ApprovalResponse:
    from ..actions.policies import APPROVAL_TTL_S

    state = _find_state(proposal_id)
    try:
        token = approve(state, proposal_id)
    except ActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return ApprovalResponse(
        investigation=state.to_response(uses_fixtures=_uses_fixtures(state)),
        approval_token=token,
        expires_in_s=APPROVAL_TTL_S,
    )


@router.post(
    "/api/proposals/{proposal_id}/reject",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
def reject_proposal(proposal_id: str, request: RejectRequest | None = None) -> InvestigationResponse:
    state = _find_state(proposal_id)
    try:
        reject(state, proposal_id, request.reason if request else "")
    except ActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/proposals/{proposal_id}/execute",
    response_model=ExecuteResponse,
    dependencies=[Depends(require_local_origin)],
)
async def execute_proposal(proposal_id: str, request: ExecuteRequest) -> ExecuteResponse:
    state = _find_state(proposal_id)
    try:
        execution = await execute_approved(state, proposal_id, request.approval_token, request.args)
    except ActionError as exc:
        store.save(state)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return ExecuteResponse(
        investigation=state.to_response(uses_fixtures=_uses_fixtures(state)),
        execution_id=execution.execution_id,
        outcome=execution.outcome,
    )


def _find_state(proposal_id: str) -> Any:
    from ..investigations import persistence

    inv_id = persistence.find_proposal(proposal_id)
    if inv_id is None:
        raise HTTPException(status_code=404, detail=f"Unknown proposal {proposal_id!r}.")
    state = store.get(inv_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown proposal {proposal_id!r}.")
    return state
