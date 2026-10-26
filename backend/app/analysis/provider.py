"""Model provider interface: live Meta Model API + simulated fallback."""

from __future__ import annotations

from typing import Any

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

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_only: bool = False,
    ) -> dict[str, Any]:
        """One chat turn, optionally with tool definitions. Returns the assistant message."""
        settings = self._settings
        if not settings.model_api_key:
            raise ModelAnalysisError("MODEL_API_KEY is not set.")
        url = settings.model_base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": settings.model_name,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if json_only:
            payload["response_format"] = {"type": "json_object"}
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
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelAnalysisError(
                "Meta API response is missing choices[0].message."
            ) from exc
        if not isinstance(message, dict):
            raise ModelAnalysisError("Meta API returned a malformed message.")
        # Omit an empty tool_calls list: the API rejects it in history.
        result: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
        if message.get("tool_calls"):
            result["tool_calls"] = message["tool_calls"]
        return result

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        message = await self.chat(build_messages(bundle), json_only=True)
        return validate_model_output(
            str(message.get("content") or ""), bundle, self._settings.model_name
        )


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
