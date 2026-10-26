"""Incident analysis endpoints: collect evidence, analyze, assess."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from ..analysis.provider import select_provider
from ..analysis.validate import ModelAnalysisError
from ..config import SIMULATED_MODEL_NAME, load_settings
from ..diagnostics import fixtures as fx
from ..diagnostics.collector import collect_diagnostics
from ..diagnostics.service_allowlist import InvalidServiceNameError
from ..diagnostics.windows_tools import powershell_available
from ..schemas import AnalyzeRequest, IncidentAssessment, StatusResponse

router = APIRouter(tags=["incidents"])


@router.get("/api/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    settings = load_settings()
    _, mode = select_provider(settings)
    model_name = settings.model_name if mode == "live" else SIMULATED_MODEL_NAME
    return StatusResponse(
        platform=sys.platform,
        live_diagnostics_available=powershell_available(),
        model_mode=mode,
        model_name=model_name,
    )


@router.post("/api/incidents/analyze", response_model=IncidentAssessment)
async def analyze_incident(request: AnalyzeRequest) -> IncidentAssessment:
    settings = load_settings()
    try:
        bundle = collect_diagnostics(request.service_name, settings, request.use_fixtures)
    except InvalidServiceNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    warnings: list[str] = []
    provider, mode = select_provider(settings)
    if mode == "simulated":
        warnings.append(
            "MODEL_API_KEY is not set: returning clearly labeled simulated analysis "
            "(no live Meta API call was made)."
        )
    try:
        analysis = await provider.analyze(bundle)
    except ModelAnalysisError as exc:
        warnings.append(f"Live Meta API analysis failed ({exc}); substituted simulated analysis.")
        analysis = fx.build_simulated_analysis(bundle)
    return IncidentAssessment(
        incident_id=f"inc-{uuid4().hex[:12]}",
        service_name=bundle.service_name,
        created_at=datetime.now(timezone.utc),
        diagnostics=bundle,
        analysis=analysis,
        warnings=warnings,
    )
