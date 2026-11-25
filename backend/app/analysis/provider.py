"""Model provider interface: Meta cloud, local endpoint, simulated fallback.

M016 introduces a capability-declaring provider abstraction so investigation
logic never depends on one AI backend. The loop chooses direction; providers
declare what they can do (text, vision, tool calling, structured output) and
the loop adapts: a provider without vision never receives images, a provider
without tool calling gets a plan-only path instead of tool definitions.

Inference provider (where intelligence runs) is independent from diagnostic
target (which computer the evidence describes); the two are never conflated.

M019 mid-flight cancel: model calls accept a cancel scope (investigation id
+ round) and raise RoundCancelled when the technician's cancel flag lands —
the Ollama transport streams so a slow CPU generation aborts within a chunk.
Streaming stays transport-internal: only completed, validated output ever
reaches the technician, so the streaming capability remains False.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx

from ..config import Settings
from ..diagnostics import fixtures as fx
from ..schemas import AnalysisMode, AnalysisResult, DiagnosticBundle
from .prompts import build_messages
from .validate import ModelAnalysisError, validate_model_output

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .local_profiles import LocalModelProfile


class RoundCancelled(Exception):
    """The technician cancelled the round while a model call was in flight.

    Deliberately NOT a ModelAnalysisError: the loop must stop the round and
    keep collected evidence, never substitute fallback content for the
    cancelled call.
    """


# Cancel scope: (investigation id, rounds_used value the flag was filed under).
CancelScope = tuple[str, int]

_CANCEL_POLL_S = 0.25


def _flag_set(inv_id: str, round_no: int) -> bool:
    """True when a matching cancel flag exists. Never raises: a broken flag
    check must not break (or fake-cancel) a model call."""
    try:
        from ..investigations.persistence import cancel_requested
    except Exception:  # noqa: BLE001 - cancel must never break a round
        return False
    try:
        return bool(cancel_requested(inv_id, round_no))
    except Exception:  # noqa: BLE001 - cancel must never break a round
        return False


async def _await_cancellable(coro: Any, cancel_scope: CancelScope | None) -> Any:
    """Await a model-call coroutine, racing the technician's cancel flag.

    A pre-set flag aborts before any HTTP is sent. Mid-flight, the wait is
    abandoned promptly; aborting our wait does not guarantee the model
    server stops generating, only that FieldRook stops waiting for it.
    """
    if cancel_scope is None:
        return await coro
    inv_id, round_no = cancel_scope
    if _flag_set(inv_id, round_no):
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        raise RoundCancelled(
            "Round cancelled by the technician before the model call started."
        )
    task = asyncio.ensure_future(coro)
    while True:
        done, _pending = await asyncio.wait({task}, timeout=_CANCEL_POLL_S)
        if done:
            return task.result()
        if _flag_set(inv_id, round_no):
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001 - the cancel itself is the outcome
                pass
            raise RoundCancelled(
                "Round cancelled by the technician during the model call."
            )


async def await_cancellable(coro: Any, cancel_scope: CancelScope | None) -> Any:
    """Public cancel race for probes awaited outside this module.

    Same semantics as ``_await_cancellable``: a pre-set flag aborts before
    the coroutine starts; a flag set mid-wait cancels the task and raises
    ``RoundCancelled``.
    """
    return await _await_cancellable(coro, cancel_scope)


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

    async def capabilities_async(self) -> ProviderCapabilities:
        """Capabilities from an async context.

        Default providers compute capabilities locally, so the sync call is
        already safe. Providers that need bounded network I/O (the local
        endpoint) override this to keep the event loop free.
        """
        return self.capabilities()

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_only: bool = False,
        cancel_scope: CancelScope | None = None,
    ) -> dict[str, Any]:
        """One chat turn. Returns the assistant message {role, content, tool_calls?}.

        cancel_scope (investigation id + round) lets the call raise
        RoundCancelled when the technician cancels mid-flight.
        """
        ...

    def model_label(self) -> str:
        return self.name

    async def analyze(self, bundle: DiagnosticBundle) -> AnalysisResult:
        """Legacy M001 single-service analysis over any chat-capable provider."""
        message = await self.chat(build_messages(bundle), json_only=True)
        return validate_model_output(
            str(message.get("content") or ""), bundle, self.model_label()
        )


async def _post_completions(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_s: float,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        return await client.post(url, json=payload, headers=headers)


async def _chat_completions(
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    json_only: bool,
    timeout_s: float,
    api_key: str | None,
    label: str,
    cancel_scope: CancelScope | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if json_only:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = await _await_cancellable(
            _post_completions(url, payload, headers, timeout_s), cancel_scope
        )
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
        cancel_scope: CancelScope | None = None,
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
            cancel_scope,
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
        cancel_scope: CancelScope | None = None,
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

    Network probes (Ollama detection, server capabilities) are cached and
    have async variants. Async request paths must use the ``*_async`` methods
    so a slow or unreachable endpoint never blocks the event loop; sync
    accessors only read cached results.
    """

    name = "local"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.last_stats: dict[str, Any] = {}

    def capabilities(self) -> ProviderCapabilities:
        from .local_profiles import resolve_profile

        settings = self._settings
        profile = resolve_profile(settings.local_model_name)
        # Sync callers (response shaping, provider listing) must never touch
        # the network. Use caps from a previous async probe, if any.
        server_caps = known_server_caps(
            settings.local_model_url, settings.local_model_name
        )
        return self._capabilities_with(profile, server_caps)

    async def capabilities_async(self) -> ProviderCapabilities:
        """Probe server caps off the event loop, then declare capabilities."""
        from .local_profiles import resolve_profile

        settings = self._settings
        profile = resolve_profile(settings.local_model_name)
        server_caps = await cached_server_caps_async(
            settings.local_model_url, settings.local_model_name
        )
        return self._capabilities_with(profile, server_caps)

    def _capabilities_with(
        self, profile: LocalModelProfile, server_caps: list[str]
    ) -> ProviderCapabilities:
        from .local_profiles import effective_vision

        settings = self._settings
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
        """Resolved style without network I/O.

        Explicit configuration wins. Otherwise report the last cached probe.
        An endpoint that has never been probed is honestly "unresolved" —
        callers must not guess a transport. Async inference resolves it.
        """
        wanted = (self._settings.local_api or "auto").strip().lower()
        if wanted in ("openai", "ollama"):
            return wanted
        try:
            base = validate_local_model_url(self._settings.local_model_url)
        except ModelAnalysisError:
            return "unresolved"
        import time as _time

        cached = _OLLAMA_PROBE_CACHE.get(_origin_of(base))
        if cached and cached[0] > _time.monotonic():
            return "ollama" if cached[1] else "openai"
        return "unresolved"

    async def api_style_async(self, *, refresh: bool = False) -> str:
        """Resolve the API style with a probe run off the event loop.

        ``refresh`` is for the user-triggered connection test: it bypasses a
        cached negative result so recovery is detected immediately.
        """
        wanted = (self._settings.local_api or "auto").strip().lower()
        if wanted in ("openai", "ollama"):
            return wanted
        try:
            base = validate_local_model_url(self._settings.local_model_url)
        except ModelAnalysisError:
            return "unresolved"
        detected = await probe_ollama_async(base, refresh=refresh)
        return "ollama" if detected else "openai"

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
        cancel_scope: CancelScope | None = None,
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
        style = await _await_cancellable(self.api_style_async(), cancel_scope)
        if style == "ollama":
            return await self._ollama_chat(
                base, model, messages, json_only, None, None, cancel_scope
            )
        url = base + "/chat/completions"
        return await _chat_completions(
            url, model, messages, None, json_only,
            settings.model_timeout_s, None, "Local model", cancel_scope,
        )

    async def _ollama_chat(
        self,
        base: str,
        model: str,
        messages: list[dict[str, Any]],
        json_only: bool,
        num_predict: int | None,
        timeout_s: float | None = None,
        cancel_scope: CancelScope | None = None,
    ) -> dict[str, Any]:
        """Ollama native chat over a streaming transport.

        The stream assembles one completed reply: partial chunks are never
        surfaced, only the finished content after the done event. Streaming
        buys two honest gains — cancel checks that abort a slow CPU
        generation promptly (per-chunk plus a race covering the silent
        model-load window), and first-token timing in last_stats.
        """
        return await _await_cancellable(
            self._ollama_chat_stream(
                base, model, messages, json_only, num_predict, timeout_s, cancel_scope
            ),
            cancel_scope,
        )

    async def _ollama_chat_stream(
        self,
        base: str,
        model: str,
        messages: list[dict[str, Any]],
        json_only: bool,
        num_predict: int | None,
        timeout_s: float | None = None,
        cancel_scope: CancelScope | None = None,
    ) -> dict[str, Any]:
        import time as _time

        origin = _origin_of(base)
        payload: dict[str, Any] = {
            "model": model,
            "messages": _to_ollama_messages(messages),
            "stream": True,
            "think": self.think_enabled(),
        }
        if json_only:
            payload["format"] = "json"
        # Tight context: task prompts are <2K tokens, and an uncapped KV
        # cache balloons process memory (measured 14.4GB for a 2.5GB model).
        options: dict[str, Any] = {"temperature": 0.2, "num_ctx": 8192}
        if num_predict:
            options["num_predict"] = num_predict
        num_gpu = getattr(self._settings, "local_num_gpu", None)
        if num_gpu is not None:
            options["num_gpu"] = num_gpu
        payload["options"] = options
        timeout = timeout_s or self._settings.model_timeout_s
        started = _time.monotonic()
        content_parts: list[str] = []
        first_token_s: float | None = None
        chunks = 0
        final: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", origin + "/api/chat", json=payload
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise ModelAnalysisError(
                            "Local model HTTP "
                            f"{response.status_code}: "
                            f"{body.decode('utf-8', 'replace')[:300]}"
                        )
                    async for line in response.aiter_lines():
                        if cancel_scope is not None and _flag_set(*cancel_scope):
                            raise RoundCancelled(
                                "Round cancelled by the technician during the model call."
                            )
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except ValueError as exc:
                            raise ModelAnalysisError(
                                "Local model returned a malformed stream line."
                            ) from exc
                        if not isinstance(event, dict):
                            raise ModelAnalysisError(
                                "Local model returned a malformed stream event."
                            )
                        message = event.get("message")
                        if isinstance(message, dict):
                            piece = message.get("content") or ""
                            if piece:
                                if first_token_s is None:
                                    first_token_s = _time.monotonic() - started
                                content_parts.append(str(piece))
                        chunks += 1
                        if event.get("done"):
                            final = event
                            break
        except httpx.HTTPError as exc:
            raise ModelAnalysisError(
                f"Local model request failed ({type(exc).__name__}): {str(exc)[:200]}"
            ) from exc
        wall_s = _time.monotonic() - started
        if not final.get("done"):
            raise ModelAnalysisError(
                "Local model stream ended without completion."
            )
        self.last_stats = {
            "wall_s": round(wall_s, 1),
            "eval_count": final.get("eval_count"),
            "eval_duration_s": round((final.get("eval_duration") or 0) / 1e9, 1),
            "prompt_eval_count": final.get("prompt_eval_count"),
            "load_duration_s": round((final.get("load_duration") or 0) / 1e9, 1),
            "first_token_s": round(first_token_s, 2) if first_token_s is not None else None,
            "stream_chunks": chunks,
        }
        return {"role": "assistant", "content": "".join(content_parts)}

    @staticmethod
    def _task_timeout_is_transient(error: Exception) -> bool:
        """Retry only timeouts, never malformed requests or model errors.

        httpx timeout exceptions arrive wrapped by the Ollama stream as
        ModelAnalysisError. Do not retry HTTP 4xx, invalid configs, or
        malformed JSON under the guise of a model cold start.
        """
        cause: BaseException | None = error
        for _ in range(5):
            if isinstance(cause, (asyncio.TimeoutError, httpx.TimeoutException)):
                return True
            cause = cause.__cause__
            if cause is None:
                break
        return any(
            word in str(error).lower()
            for word in ("readtimeout", "connecttimeout", "pooltimeout", "timeout")
        )

    async def run_task(
        self,
        task: str,
        prompt: str,
        timeout_s: float | None = None,
        images: list[str] | None = None,
        cancel_scope: CancelScope | None = None,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """One bounded task wall-clock budget, with one timeout-only triage retry.

        Prior behavior gave EACH HTTP read a fresh timeout and could then
        invoke an unbounded second JSON repair call. On a cold Ollama load
        this meant a '120 s' triage could exceed its advertised budget.
        A short second chance may recover a transient first-load timeout,
        but both attempts AND JSON repair share one deadline.
        RoundCancelled propagates immediately and is never a fallback.
        """
        import time as _time

        from .local_tasks import TASK_LIMITS, extract_json, missing_keys

        limits = TASK_LIMITS.get(task, {"num_predict": 300, "timeout": 120})
        settings = self._settings
        base = validate_local_model_url(settings.local_model_url)
        model = settings.local_model_name.strip()
        if not model:
            raise ModelAnalysisError("FIELDROOK_LOCAL_MODEL_NAME is not set.")
        warnings: list[str] = []
        total_budget = float(timeout_s or limits["timeout"])
        if total_budget <= 0:
            raise ModelAnalysisError("Local task timeout must be positive.")
        started = _time.monotonic()
        deadline = started + total_budget
        self.last_stats = {
            "task": task,
            "status": "started",
            "attempts": 0,
            "retry_used": False,
        }
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

        # Triage alone gets a reserved tail of up to 25s for one transient
        # timeout retry; other tasks use a single attempt to avoid duplicate
        # work on slow local hardware. No retry for invalid JSON.
        retry_reserve = min(25.0, total_budget * 0.25) if task == "triage" else 0.0
        first_attempt_budget = max(0.01, total_budget - retry_reserve)
        attempts = 0
        retry_used = False

        async def invoke() -> dict[str, Any]:
            # Probing and inference are both inside the wall-clock deadline.
            style = await _await_cancellable(self.api_style_async(), cancel_scope)
            remaining = max(0.01, deadline - _time.monotonic())
            if style == "ollama":
                return await self._ollama_chat(
                    base, model, messages, True, num_predict, remaining, cancel_scope
                )
            return await _chat_completions(
                base + "/chat/completions", model, messages, None,
                True, remaining, None, "Local model", cancel_scope,
            )

        reply: dict[str, Any] | None = None
        for attempt in range(1, 3 if task == "triage" else 2):
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                break
            per_attempt_budget = min(
                remaining, first_attempt_budget if attempt == 1 else remaining
            )
            attempts = attempt
            self.last_stats["attempts"] = attempts
            try:
                reply = await asyncio.wait_for(
                    invoke(), timeout=per_attempt_budget
                )
                break
            except (asyncio.TimeoutError, ModelAnalysisError) as exc:
                elapsed = _time.monotonic() - started
                transient = self._task_timeout_is_transient(exc)
                if (
                    task == "triage"
                    and attempt == 1
                    and transient
                    and deadline - _time.monotonic() > 0.01
                ):
                    retry_used = True
                    warnings.append(
                        "triage first model attempt timed out; one bounded "
                        "retry within the same task deadline."
                    )
                    continue
                self.last_stats.update({
                    "status": "failed",
                    "attempts": attempts,
                    "retry_used": retry_used,
                    "task_wall_s": round(elapsed, 2),
                    "failure_kind": "timeout" if transient else "model_error",
                })
                return None, warnings + [
                    f"{task} model call failed "
                    f"({'timeout' if transient else 'model error'}); "
                    "no model reasoning; deterministic fallback fills in."
                ]

        if reply is None:
            self.last_stats.update({
                "status": "failed",
                "attempts": attempts,
                "retry_used": retry_used,
                "task_wall_s": round(_time.monotonic() - started, 2),
                "failure_kind": "deadline",
            })
            return None, warnings + [
                f"{task} exceeded its {total_budget:g}s wall-clock budget; "
                "no model reasoning; deterministic fallback fills in."
            ]

        text = str(reply.get("content") or "")
        parsed = extract_json(text)
        if parsed is None:
            remaining = deadline - _time.monotonic()
            repaired = None
            if remaining > 0.1:
                try:
                    repaired = await asyncio.wait_for(
                        self._repair_json(
                            task, text, base, model, num_predict, remaining,
                            cancel_scope,
                        ),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    warnings.append(
                        f"{task} JSON repair exceeded the shared task deadline."
                    )
            if repaired is None:
                self.last_stats.update({
                    "task": task,
                    "status": "failed",
                    "attempts": attempts,
                    "retry_used": retry_used,
                    "task_wall_s": round(_time.monotonic() - started, 2),
                    "failure_kind": "invalid_json",
                })
                return None, warnings + [
                    f"{task} returned unusable JSON; no model reasoning; "
                    "deterministic fallback fills in."
                ]
            warnings.append(f"{task} needed one JSON repair retry.")
            parsed = repaired

        gaps = missing_keys(parsed, task)
        if gaps:
            warnings.append(f"{task} is missing keys {gaps}; partial content used.")
        # Keep successful per-model token stats from the transport, with new
        # task-level provenance. No stale success stats on a failed task.
        self.last_stats.update({
            "task": task,
            "status": "model",
            "attempts": attempts,
            "retry_used": retry_used,
            "task_wall_s": round(_time.monotonic() - started, 2),
        })
        if retry_used:
            warnings.append(
                f"{task} recovered on its single bounded timeout retry; "
                "model-generated output was returned."
            )
        return parsed, warnings

    async def _repair_json(
        self,
        task: str,
        text: str,
        base: str,
        model: str,
        num_predict: int,
        timeout: float,
        cancel_scope: CancelScope | None = None,
    ) -> dict[str, Any] | None:
        from .local_tasks import extract_json

        prompt = (
            "Your previous reply was not valid JSON. Reply with ONLY the corrected "
            f"JSON object for the {task} task, no other text. Previous reply "
            f"(truncated): {text.strip()[:1200]}"
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            style = await _await_cancellable(self.api_style_async(), cancel_scope)
            if style == "ollama":
                reply = await self._ollama_chat(
                    base, model, messages, True, num_predict, timeout, cancel_scope
                )
            else:
                reply = await _chat_completions(
                    base + "/chat/completions", model, messages, None, True,
                    timeout, None, "Local model", cancel_scope,
                )
        except ModelAnalysisError:
            return None
        return extract_json(str(reply.get("content") or ""))


def _origin_of(base: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(base)
    return f"{parsed.scheme}://{parsed.netloc}"


def _validated_origin(raw_url: str) -> str | None:
    """Loopback origin for a URL, or None when the URL is not loopback.

    Defense in depth: every network entry point validates here even if a
    caller already validated, so a direct call can never reach a remote host.
    """
    try:
        return _origin_of(validate_local_model_url(raw_url))
    except ModelAnalysisError:
        return None


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
    """True when the origin answers like Ollama. Cached; never raises.

    Sync callers only (scripts, tests). Async request paths must use
    ``probe_ollama_async`` so a slow endpoint cannot freeze the event loop.
    """
    import time as _time

    import httpx as _httpx

    origin = _validated_origin(base)
    if origin is None:
        return False
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


def cached_ollama_probe(base: str) -> bool:
    """Last probe answer without network I/O; False when absent or expired."""
    import time as _time

    cached = _OLLAMA_PROBE_CACHE.get(_origin_of(base))
    return bool(cached and cached[0] > _time.monotonic() and cached[1])


async def probe_ollama_async(base: str, *, refresh: bool = False) -> bool:
    """Async Ollama probe: same cache and verdicts, never blocks the loop.

    If refresh=True, bypasses any cached results to force a fresh probe.
    """
    import time as _time

    origin = _validated_origin(base)
    if origin is None:
        return False
    now = _time.monotonic()
    cached = _OLLAMA_PROBE_CACHE.get(origin)
    if cached and cached[0] > now and not refresh:
        return cached[1]
    result = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(origin + "/api/tags")
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

    safe_origin = _validated_origin(origin)
    if safe_origin is None:
        return []
    try:
        with _httpx.Client(timeout=timeout) as client:
            response = client.post(safe_origin + "/api/show", json={"model": model})
        if response.status_code != 200:
            return []
        data = response.json()
        caps = data.get("capabilities")
        return [str(cap) for cap in caps] if isinstance(caps, list) else []
    except Exception:  # noqa: BLE001 - unknown server, unknown caps
        return []


def cached_server_caps(raw_url: str, model: str) -> list[str]:
    """Cached server caps; empty on any failure (never raises, never assumes).

    Sync callers only. Async request paths must use
    ``cached_server_caps_async``.
    """
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


def known_server_caps(raw_url: str, model: str) -> list[str]:
    """Caps already learned by a prior probe; no network I/O, no assumptions.

    Used by sync response shaping so a cached Ollama verdict can still gate
    vision without risking a blocking request on the event loop.
    """
    import time as _time

    try:
        base = validate_local_model_url(raw_url)
    except ModelAnalysisError:
        return []
    origin = _origin_of(base)
    now = _time.monotonic()
    probe = _OLLAMA_PROBE_CACHE.get(origin)
    if not probe or probe[0] <= now or not probe[1]:
        return []
    cached = _SERVER_CAPS_CACHE.get((origin, (model or "").strip()))
    if cached and cached[0] > now:
        return cached[1]
    return []


async def fetch_server_caps_async(
    origin: str, model: str, timeout: float = 8.0
) -> list[str]:
    """Async /api/show probe: same verdicts as fetch_server_caps."""
    safe_origin = _validated_origin(origin)
    if safe_origin is None:
        return []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(safe_origin + "/api/show", json={"model": model})
        if response.status_code != 200:
            return []
        data = response.json()
        caps = data.get("capabilities")
        return [str(cap) for cap in caps] if isinstance(caps, list) else []
    except Exception:  # noqa: BLE001 - unknown server, unknown caps
        return []


async def cached_server_caps_async(
    raw_url: str, model: str, *, refresh: bool = False
) -> list[str]:
    """Async cached caps; explicit tests may refresh stale capabilities."""
    import time as _time

    try:
        base = validate_local_model_url(raw_url)
    except ModelAnalysisError:
        return []
    if not await probe_ollama_async(base):
        return []
    key = (_origin_of(base), (model or "").strip())
    now = _time.monotonic()
    cached = _SERVER_CAPS_CACHE.get(key)
    if cached and cached[0] > now and not refresh:
        return cached[1]
    caps = await fetch_server_caps_async(key[0], key[1])
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
