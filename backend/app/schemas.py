"""Pydantic schemas for evidence, analysis, and incident assessments."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Likelihood = Literal["high", "medium", "low"]
BundleMode = Literal["live", "fixture"]
AnalysisMode = Literal["live", "simulated"]


class ServiceSummary(BaseModel):
    name: str
    display_name: str
    status: str


class ServiceListResponse(BaseModel):
    services: list[ServiceSummary]
    mode: BundleMode
    warnings: list[str] = Field(default_factory=list)
    collected_at: datetime


class EvidenceItem(BaseModel):
    id: str
    category: str  # service_status | startup_type | event_log
    source: str  # e.g. "powershell:Get-Service" or "fixture:services"
    collected_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DiagnosticBundle(BaseModel):
    service_name: str
    display_name: str | None = None
    collected_at: datetime
    mode: BundleMode
    items: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ObservedFact(BaseModel):
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)


class RootCause(BaseModel):
    title: str
    description: str
    likelihood: Likelihood = "low"
    evidence_ids: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    summary: str
    facts: list[ObservedFact] = Field(default_factory=list)
    causes: list[RootCause] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    explanation: str
    mode: AnalysisMode
    model: str
    validation_warnings: list[str] = Field(default_factory=list)


class IncidentAssessment(BaseModel):
    incident_id: str
    service_name: str
    created_at: datetime
    diagnostics: DiagnosticBundle
    analysis: AnalysisResult
    warnings: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    service_name: str
    use_fixtures: bool | None = None


class StatusResponse(BaseModel):
    service: str = "fieldrook-api"
    version: str = "0.1.0"
    platform: str
    live_diagnostics_available: bool
    model_mode: AnalysisMode
    model_name: str
    fixtures_available: bool = True
