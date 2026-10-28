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


# Server-capability cache: (origin, model) -> (expires_at, [caps]).
# Loopback GETs only; a miss degrades to "unknown", never to assumption.
_SERVER_CAPS_CACHE: dict[tuple[str, str], tuple[float, list[str]]] = {}
_SERVER_CAPS_TTL_S = 300.0
# Ollama probe cache: origin -> (expires_at, is_ollama).
_OLLAMA_PROBE_CACHE: dict[str, tuple[float, bool]] = {}


class LocalEndpointProvider(ModelProvider):
    """Optional local inference server (Ollama, llama.cpp) over loopback.

    Two API styles: generic OpenAI-compatible chat completions, or the
    Ollama native API when the server probes as Ollama. The native style is
    required for thinking control (measured: /v1 ignores think=false and a
    thinking model then burns 100s+ per call) and for token statistics.

    The local path never uses chat tool-calling: small models reason through
    the task pipeline (triage/plan/reassess) with tight token caps instead.
    Capabilities come from explicit configuration plus curated profiles,
    never from the model name alone.
    """

    name = "local"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.last_stats: dict[str, Any] = {}

    def capabilities(self) -> ProviderCapabilities:
        from .local_profiles import effective_vision, resolve_profile

        settings = self._settings
        profile = resolve_profile(settings.local_model_name)
        server_caps = cached_server_caps(
            settings.local_model_url, settings.local_model_name
        )
        return ProviderCapabilities(
            text=True,
            vision=effective_vision(settings.local_model_vision, profile, server_caps),
            tool_calling=False,
            structured_output=False,
            streaming=False,
            processing_location="local",
        )

    def model_label(self) -> str:
        name = self._settings.local_model_name or "local-model"
        return f"local/{name}"

    def api_style(self) -> str:
        """Resolved API style: explicit config, else a cached Ollama probe."""
        wanted = (self._settings.local_api or "auto").strip().lower()
        if wanted in ("openai", "ollama"):
            return wanted
        try:
            base = validate_local_model_url(self._settings.local_model_url)
        except ModelAnalysisError:
            return "openai"
        return "ollama" if probe_ollama(base) else "openai"

    def think_enabled(self) -> bool:
        """Thinking defaults OFF for task calls; the operator may force it on."""
        setting = (self._settings.local_think or "auto").strip().lower()
        if setting == "on":
            return True
        return False

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
        if tools:
            raise ModelAnalysisError(
                "The local path does not use chat tool-calling; reasoning runs "
                "through the task pipeline instead."
            )
        # Local servers do not need the cloud key; never send it there.
        if self.api_style() == "ollama":
            return await self._ollama_chat(base, model, messages, json_only, None)
        url = base + "/chat/completions"
        return await _chat_completions(
            url, model, messages, None, json_only,
            settings.model_timeout_s, None, "Local model",
        )

    async def _ollama_chat(
        self,
        base: str,
        model: str,
        messages: list[dict[str, Any]],
        json_only: bool,
        num_predict: int | None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        import time as _time

        origin = _origin_of(base)
        payload: dict[str, Any] = {
            "model": model,
            "messages": _to_ollama_messages(messages),
            "stream": False,
            "think": self.think_enabled(),
        }
        if json_only:
            payload["format"] = "json"
        # Tight context: task prompts are <2K tokens, and an uncapped KV
        # cache balloons process memory (measured 14.4GB for a 2.5GB model).
        options: dict[str, Any] = {"temperature": 0.2, "num_ctx": 8192}
        if num_predict:
            options["num_predict"] = num_predict
        payload["options"] = options
        timeout = timeout_s or self._settings.model_timeout_s
        started = _time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(origin + "/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ModelAnalysisError(
                f"Local model request failed ({type(exc).__name__}): {str(exc)[:200]}"
            ) from exc
        wall_s = _time.monotonic() - started
        if response.status_code != 200:
            raise ModelAnalysisError(
                f"Local model HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ModelAnalysisError("Local model returned a non-JSON response.") from exc
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, dict):
            raise ModelAnalysisError("Local model response is missing message.")
        self.last_stats = {
            "wall_s": round(wall_s, 1),
            "eval_count": data.get("eval_count"),
            "eval_duration_s": round((data.get("eval_duration") or 0) / 1e9, 1),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "load_duration_s": round((data.get("load_duration") or 0) / 1e9, 1),
        }
        return {"role": "assistant", "content": str(message.get("content") or "")}

    async def run_task(
        self,
        task: str,
        prompt: str,
        timeout_s: float | None = None,
        images: list[str] | None = None,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Run one pipeline task; returns (parsed payload or None, warnings).

        One bounded repair retry on JSON-parse failure; schema gaps return
        partial content with a warning instead of retrying forever.
        `images` (base64, no data prefix) attaches screenshots for
        vision-capable models; callers must capability-gate first.
        """
        from .local_tasks import TASK_LIMITS, extract_json, missing_keys

        limits = TASK_LIMITS.get(task, {"num_predict": 300, "timeout": 120})
        settings = self._settings
        base = validate_local_model_url(settings.local_model_url)
        model = settings.local_model_name.strip()
        if not model:
            raise ModelAnalysisError("FIELDROOK_LOCAL_MODEL_NAME is not set.")
        warnings: list[str] = []
        timeout = timeout_s or float(limits["timeout"])
        num_predict = int(limits["num_predict"])
        try:
            from .local_profiles import resolve_profile

            scale = resolve_profile(model).task_budget_scale
            num_predict = int(num_predict * scale)
        except Exception:  # noqa: BLE001 - profile failure keeps defaults
            pass
        if images:
            content: str | list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for blob in images[:4]:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{blob}"},
                    }
                )
            messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]
        try:
            if self.api_style() == "ollama":
                reply = await self._ollama_chat(base, model, messages, True, num_predict, timeout)
            else:
                url = base + "/chat/completions"
                reply = await _chat_completions(
                    url, model, messages, None, True, timeout, None, "Local model",
                )
        except ModelAnalysisError as exc:
            return None, [f"{task} call failed ({exc}); deterministic fallback fills in."]
        text = str(reply.get("content") or "")
        parsed = extract_json(text)
        if parsed is None:
            repaired = await self._repair_json(task, text, base, model, num_predict, timeout)
            if repaired is None:
                return None, [f"{task} returned unparseable output; deterministic fallback fills in."]
            warnings.append(f"{task} needed one JSON repair retry.")
            parsed = repaired
        gaps = missing_keys(parsed, task)
        if gaps:
            warnings.append(f"{task} is missing keys {gaps}; partial content used.")
        return parsed, warnings

    async def _repair_json(
        self, task: str, text: str, base: str, model: str, num_predict: int, timeout: float
    ) -> dict[str, Any] | None:
        from .local_tasks import extract_json

        prompt = (
            "Your previous reply was not valid JSON. Reply with ONLY the corrected "
            f"JSON object for the {task} task, no other text. Previous reply "
            f"(truncated): {text.strip()[:1200]}"
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            if self.api_style() == "ollama":
                reply = await self._ollama_chat(base, model, messages, True, num_predict, timeout)
            else:
                reply = await _chat_completions(
                    base + "/chat/completions", model, messages, None, True,
                    timeout, None, "Local model",
                )
        except ModelAnalysisError:
            return None
        return extract_json(str(reply.get("content") or ""))


def _origin_of(base: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(base)
    return f"{parsed.scheme}://{parsed.netloc}"


def _to_ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style messages (incl. image parts) to Ollama form."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            converted.append({"role": message.get("role", "user"), "content": content})
            continue
        texts: list[str] = []
        images: list[str] = []
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                texts.append(str(part["text"]))
            elif part.get("type") == "image_url":
                url = ((part.get("image_url") or {}).get("url") or "")
                if url.startswith("data:") and ";base64," in url:
                    images.append(url.split(";base64,", 1)[1])
        entry: dict[str, Any] = {
            "role": message.get("role", "user"),
            "content": "\n".join(texts),
        }
        if images:
            entry["images"] = images
        converted.append(entry)
    return converted


def probe_ollama(base: str) -> bool:
    """True when the origin answers like Ollama. Cached; never raises."""
    import time as _time

    import httpx as _httpx

    origin = _origin_of(base)
    now = _time.monotonic()
    cached = _OLLAMA_PROBE_CACHE.get(origin)
    if cached and cached[0] > now:
        return cached[1]
    result = False
    try:
        with _httpx.Client(timeout=5.0) as client:
            response = client.get(origin + "/api/tags")
        if response.status_code == 200:
            data = response.json()
            result = isinstance(data, dict) and isinstance(data.get("models"), list)
    except Exception:  # noqa: BLE001 - probe failure means "not Ollama"
        result = False
    _OLLAMA_PROBE_CACHE[origin] = (now + _SERVER_CAPS_TTL_S, result)
    return result


def fetch_server_caps(origin: str, model: str, timeout: float = 8.0) -> list[str]:
    """Server-advertised model capabilities via /api/show (Ollama)."""
    import httpx as _httpx

    try:
        with _httpx.Client(timeout=timeout) as client:
            response = client.post(origin + "/api/show", json={"model": model})
        if response.status_code != 200:
            return []
        data = response.json()
        caps = data.get("capabilities")
        return [str(cap) for cap in caps] if isinstance(caps, list) else []
    except Exception:  # noqa: BLE001 - unknown server, unknown caps
        return []


def cached_server_caps(raw_url: str, model: str) -> list[str]:
    """Cached server caps; empty on any failure (never raises, never assumes)."""
    import time as _time

    try:
        base = validate_local_model_url(raw_url)
    except ModelAnalysisError:
        return []
    if not probe_ollama(base):
        return []
    key = (_origin_of(base), (model or "").strip())
    now = _time.monotonic()
    cached = _SERVER_CAPS_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]
    caps = fetch_server_caps(key[0], key[1])
    _SERVER_CAPS_CACHE[key] = (now + _SERVER_CAPS_TTL_S, caps)
    return caps


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
