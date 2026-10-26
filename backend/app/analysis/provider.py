"""Model provider interface: live Meta Model API + simulated fallback."""

from __future__ import annotations

import httpx

from ..config import Settings
from ..diagnostics import fixtures as fx
from ..schemas import AnalysisMode, AnalysisResult, DiagnosticBundle
from .prompts import build_messages
from .validate import ModelAnalysisError, validate_model_output


class MetaModelProvider:
    """Calls the Meta Model API (OpenAI-compatible chat completions)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        settings = self._settings
        if not settings.model_api_key:
            raise ModelAnalysisError("MODEL_API_KEY is not set.")
        url = settings.model_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": settings.model_name,
            "messages": build_messages(bundle),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {settings.model_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=settings.model_timeout_s) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise ModelAnalysisError(
                f"Meta API request failed ({type(exc).__name__}): {str(exc)[:200]}"
            ) from exc
        if response.status_code != 200:
            raise ModelAnalysisError(
                f"Meta API HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ModelAnalysisError("Meta API returned a non-JSON response.") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelAnalysisError(
                "Meta API response is missing choices[0].message.content."
            ) from exc
        return validate_model_output(str(content or ""), bundle, settings.model_name)


class SimulatedProvider:
    """Deterministic offline analysis. Never claims a live model call."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        return fx.build_simulated_analysis(bundle)


def select_provider(settings: Settings) -> tuple[MetaModelProvider | SimulatedProvider, AnalysisMode]:
    if settings.model_api_key:
        return MetaModelProvider(settings), "live"
    return SimulatedProvider(settings), "simulated"
