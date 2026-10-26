"""Service listing and per-service diagnostic endpoints (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..config import load_settings
from ..diagnostics.collector import collect_diagnostics, list_services_collected
from ..diagnostics.service_allowlist import InvalidServiceNameError
from ..diagnostics.windows_tools import DiagnosticCommandError
from ..schemas import DiagnosticBundle, ServiceListResponse

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=ServiceListResponse)
def get_services(
    use_fixtures: bool | None = Query(default=None),
) -> ServiceListResponse:
    settings = load_settings()
    try:
        return list_services_collected(settings, use_fixtures)
    except DiagnosticCommandError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{name}/diagnostics", response_model=DiagnosticBundle)
def get_service_diagnostics(
    name: str, use_fixtures: bool | None = Query(default=None)
) -> DiagnosticBundle:
    settings = load_settings()
    try:
        return collect_diagnostics(name, settings, use_fixtures)
    except InvalidServiceNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
