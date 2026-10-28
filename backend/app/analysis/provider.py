"""Model provider interface: Meta cloud, local endpoint, simulated fallback.

M016 introduces a capability-declaring provider abstraction so investigation
logic never depends on one AI backend. The loop chooses direction; providers
declare what they can do (text, vision, tool calling, structured output) and
the loop adapts: a provider without vision never receives images, a provider
without tool calling gets a plan-only path instead of tool definitions.

Inference provider (where intelligence runs) is independent from diagnostic
target (which computer the evidence describes); the two are never conflated.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import Settings
from ..diagnostics import fixtures as fx
from ..schemas import AnalysisMode, AnalysisResult, DiagnosticBundle
from .prompts import build_messages
from .validate import ModelAnalysisError, validate_model_output


@dataclass(frozen=True)
class ProviderCapabilities:
    """Advertised abilities. The loop enforces these; providers never do more."""

    text: bool = True
    vision: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    streaming: bool = False
    # Where prompt content is processed. Drives consent wording and privacy gates.
    processing_location: str = "none"  # "cloud" | "local" | "none"


class ModelProvider(ABC):
    """One inference backend behind a uniform chat interface."""

    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_only: bool = False,
    ) -> dict[str, Any]:
        """One chat turn. Returns the assistant message {role, content, tool_calls?}."""
        ...

    def model_label(self) -> str:
        return self.name

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        """Legacy M001 single-service analysis over any chat-capable provider."""
        message = await self.chat(build_messages(bundle), json_only=True)
        return validate_model_output(
            str(message.get("content") or ""), bundle, self.model_label()
        )


async def _chat_completions(
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    json_only: bool,
    timeout_s: float,
    api_key: str | None,
    label: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if json_only:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise ModelAnalysisError(
            f"{label} request failed ({type(exc).__name__}): {str(exc)[:200]}"
        ) from exc
    if response.status_code != 200:
        raise ModelAnalysisError(f"{label} HTTP {response.status_code}: {response.text[:300]}")
    try:
        data = response.json()
    except ValueError as exc:
        raise ModelAnalysisError(f"{label} returned a non-JSON response.") from exc
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelAnalysisError(
            f"{label} response is missing choices[0].message."
        ) from exc
    if not isinstance(message, dict):
        raise ModelAnalysisError(f"{label} returned a malformed message.")
    # Omit an empty tool_calls list: chat APIs reject it in history.
    result: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("tool_calls"):
        result["tool_calls"] = message["tool_calls"]
    return result


class MetaModelProvider(ModelProvider):
    """Calls the Meta Model API (OpenAI-compatible chat completions)."""

    name = "meta"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            text=True,
            vision=True,
            tool_calling=True,
            structured_output=True,
            streaming=False,
            processing_location="cloud",
        )

    def model_label(self) -> str:
        return self._settings.model_name

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_only: bool = False,
    ) -> dict[str, Any]:
        settings = self._settings
        if settings.offline_mode:
            raise ModelAnalysisError("FIELDROOK_OFFLINE is enabled; live model calls are forbidden.")
        if not settings.model_api_key:
            raise ModelAnalysisError("MODEL_API_KEY is not set.")
        url = settings.model_base_url.rstrip("/") + "/chat/completions"
        return await _chat_completions(
            url,
            settings.model_name,
            messages,
            tools,
            json_only,
            settings.model_timeout_s,
            settings.model_api_key,
            "Meta API",
        )

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        message = await self.chat(build_messages(bundle), json_only=True)
        return validate_model_output(
            str(message.get("content") or ""), bundle, self._settings.model_name
        )


class SimulatedProvider(ModelProvider):
    """Deterministic offline analysis. Never claims a live model call."""

    name = "simulated"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            text=True,
            vision=False,
            tool_calling=False,
            structured_output=True,
            streaming=False,
            processing_location="none",
        )

    def model_label(self) -> str:
        from ..config import SIMULATED_MODEL_NAME

        return SIMULATED_MODEL_NAME

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_only: bool = False,
    ) -> dict[str, Any]:
        raise ModelAnalysisError(
            "The simulated provider does not take chat turns; the loop runs "
            "deterministic fixture diagnostics instead."
        )

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        return fx.build_simulated_analysis(bundle)


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def validate_local_model_url(raw_url: str) -> str:
    """Accept only http(s) loopback endpoints; reject everything else.

    A local provider must not become a confused-deputy channel to arbitrary
    remote endpoints, so anything that is not an explicit loopback URL is
    refused before any request is made.
    """
    text = (raw_url or "").strip().rstrip("/")
    if not text:
        raise ModelAnalysisError(
            "FIELDROOK_LOCAL_MODEL_URL is not set; configure a loopback model "
            "endpoint (e.g. http://127.0.0.1:11434/v1) to use the local provider."
        )
    try:
        parsed = urlparse(text if "://" in text else f"http://{text}")
    except ValueError as exc:
        raise ModelAnalysisError(f"Local model URL is not parseable: {exc}") from exc
    if parsed.scheme not in ("http", "https"):
        raise ModelAnalysisError("Local model URL must use http or https.")
    host = (parsed.hostname or "").lower().strip("[]")
    if host not in LOOPBACK_HOSTS:
        raise ModelAnalysisError(
            f"Local model URL host {host!r} is not loopback; refusing to send "
            "investigation content to a non-local endpoint."
        )
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


class LocalEndpointProvider(ModelProvider):
    """Optional OpenAI-compatible local inference server (Ollama, llama.cpp).

    Capabilities come from explicit configuration, never assumption: a local
    model is text-only without tool calling unless the operator enables those
    flags for a model known to support them.
    """

    name = "local"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            text=True,
            vision=self._settings.local_model_vision,
            tool_calling=self._settings.local_model_tools,
            structured_output=False,
            streaming=False,
            processing_location="local",
        )

    def model_label(self) -> str:
        name = self._settings.local_model_name or "local-model"
        return f"local/{name}"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_only: bool = False,
    ) -> dict[str, Any]:
        settings = self._settings
        base = validate_local_model_url(settings.local_model_url)
        model = settings.local_model_name.strip()
        if not model:
            raise ModelAnalysisError(
                "FIELDROOK_LOCAL_MODEL_NAME is not set; name the model the local "
                "server should run."
            )
        url = base + "/chat/completions"
        # Local servers do not need the cloud key; never send it there.
        return await _chat_completions(
            url, model, messages, tools, json_only,
            settings.model_timeout_s, None, "Local model",
        )


def select_provider(
    settings: Settings, override: str | None = None
) -> tuple[ModelProvider, AnalysisMode]:
    """Pick the inference provider.

    `override` ("meta" | "simulated" | "local") wins over
    FIELDROOK_MODEL_PROVIDER, which wins over "auto". Offline mode forces
    simulated for cloud providers but still allows an explicitly selected
    local endpoint: local inference makes no network call beyond loopback.
    """
    wanted = (override or settings.model_provider or "auto").strip().lower()
    if wanted not in ("auto", "meta", "simulated", "local"):
        wanted = "auto"
    if wanted == "simulated":
        return SimulatedProvider(settings), "simulated"
    if wanted == "local":
        return LocalEndpointProvider(settings), "live"
    if wanted == "meta":
        if settings.offline_mode:
            raise ModelAnalysisError("FIELDROOK_OFFLINE is enabled; live model calls are forbidden.")
        if not settings.model_api_key:
            raise ModelAnalysisError("MODEL_API_KEY is not set.")
        return MetaModelProvider(settings), "live"
    # auto: legacy behavior
    if settings.model_api_key and not settings.offline_mode:
        return MetaModelProvider(settings), "live"
    return SimulatedProvider(settings), "simulated"
