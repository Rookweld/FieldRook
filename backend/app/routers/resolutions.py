"""Resolution plans and Confirm Fix verification endpoints (M008).

Plans turn findings into explicit measurable criteria; Confirm Fix grades
fresh measurements against them. Nothing here authorizes or executes
actions: interventions link real executions, and verification runs
read-only diagnostics only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import load_settings
from ..investigations.store import store
from ..resolutions import service as plans
from ..resolutions.service import PlanBudgetError, PlanError
from ..schemas import InvestigationResponse
from .actions import require_local_origin

router = APIRouter(tags=["resolutions"])


class CriterionDraft(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    tool_name: str = Field(min_length=1, max_length=64)
    tool_args: dict[str, Any] = Field(default_factory=dict)
    path: str = Field(min_length=1, max_length=128)
    op: str = Field(min_length=1, max_length=16)
    expected: Any = None


class PlanCreateRequest(BaseModel):
    problem: str = Field(default="", max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list)
    intended_state: str = Field(min_length=1, max_length=2000)
    criteria: list[CriterionDraft] = Field(default_factory=list)
    guidance: str = Field(default="", max_length=2000)
    risks: str = Field(default="", max_length=2000)
    remediation_kind: str = Field(default="manual", max_length=16)
    action_id: str | None = Field(default=None, max_length=64)
    target: str | None = Field(default=None, max_length=64)


class ManualInterventionRequest(BaseModel):
    description: str = Field(min_length=1, max_length=1000)


class LinkExecutionRequest(BaseModel):
    execution_id: str = Field(min_length=1, max_length=64)


def _uses_fixtures(state: Any) -> bool:
    return state.mode == "simulated"


def _find_plan(plan_id: str) -> tuple[Any, Any]:
    from ..investigations import persistence

    inv_id = persistence.find_plan(plan_id)
    if inv_id is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan {plan_id!r}.")
    state = store.get(inv_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan {plan_id!r}.")
    plan = next((p for p in state.plans if p.plan_id == plan_id), None)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan {plan_id!r}.")
    return state, plan


@router.get("/api/plans/template")
def plan_template(action_id: str) -> dict[str, Any]:
    try:
        return plans.plan_template(action_id)
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/plans/{plan_id}", response_model=InvestigationResponse)
def get_plan(plan_id: str) -> InvestigationResponse:
    state, _ = _find_plan(plan_id)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/investigations/{investigation_id}/plans",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
def create_plan(investigation_id: str, request: PlanCreateRequest) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    try:
        plans.create_plan(state, request.model_dump())
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/plans/{plan_id}/baseline",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
async def capture_baseline(plan_id: str) -> InvestigationResponse:
    state, plan = _find_plan(plan_id)
    settings = load_settings()
    try:
        await plans.capture_baseline(state, plan, settings)
    except PlanBudgetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanError as exc:
        status = 422 if "measurable" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/plans/{plan_id}/interventions/manual",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
def record_manual(plan_id: str, request: ManualInterventionRequest) -> InvestigationResponse:
    state, plan = _find_plan(plan_id)
    try:
        plans.record_manual_intervention(state, plan, request.description)
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/plans/{plan_id}/interventions/link-execution",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
def link_execution(plan_id: str, request: LinkExecutionRequest) -> InvestigationResponse:
    state, plan = _find_plan(plan_id)
    try:
        plans.link_execution(state, plan, request.execution_id)
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))


@router.post(
    "/api/plans/{plan_id}/verify",
    response_model=InvestigationResponse,
    dependencies=[Depends(require_local_origin)],
)
async def verify_plan(plan_id: str) -> InvestigationResponse:
    state, plan = _find_plan(plan_id)
    settings = load_settings()
    try:
        await plans.verify_plan(state, plan, settings)
    except PlanBudgetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state.to_response(uses_fixtures=_uses_fixtures(state))
