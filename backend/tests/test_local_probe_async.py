"""M030: local Ollama probes must never block the event loop.

The local endpoint's API style and server capabilities used to be resolved by
synchronous ``httpx.Client`` calls from inside async functions (and from the
provider listing). These tests pin the fix:

- async paths use ``*_async`` helpers and keep the loop responsive;
- sync accessors (response shaping, ``GET /api/providers``) never touch the
  network;
- successful, slow and unreachable loopback endpoints degrade honestly.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from app.analysis import provider as provider_module
from app.analysis.provider import (
    LocalEndpointProvider,
    cached_server_caps_async,
    probe_ollama_async,
)
from app.config import Settings
from app.main import app

client = TestClient(app)


class _OllamaHandler(BaseHTTPRequestHandler):
    """Tiny loopback stand-in for Ollama's /api/tags and /api/show."""

    def _send(self, body: dict[str, object]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        if self.path != "/api/tags":
            self.send_response(404)
            self.end_headers()
            return
        self.server.tags_hits = getattr(self.server, "tags_hits", 0) + 1
        self.server.auth_headers.append((self.path, self.headers.get("Authorization")))
        started = getattr(self.server, "tags_started", None)
        if started is not None:
            started.set()
        time.sleep(getattr(self.server, "delay", 0.0))
        if not getattr(self.server, "tags_enabled", True):
            self.send_response(404)
            self.end_headers()
            return
        self._send({"models": [{"name": "uncurated:1b"}]})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.server.auth_headers.append((self.path, self.headers.get("Authorization")))
        if self.path == "/api/chat":
            self._send({"message": {"content": "OK"}, "done": True})
            return
        if self.path == "/v1/chat/completions":
            self._send({"choices": [{"message": {"content": "OK"}}]})
            return
        if self.path != "/api/show":
            self.send_response(404)
            self.end_headers()
            return
        started = getattr(self.server, "show_started", None)
        if started is not None:
            started.set()
        time.sleep(getattr(self.server, "show_delay", getattr(self.server, "delay", 0.0)))
        self._send({"capabilities": list(getattr(self.server, "caps", []))})

    def log_message(self, *args: object) -> None:  # noqa: D401 - silence
        return


@pytest.fixture(autouse=True)
def _clear_probe_caches():
    provider_module._OLLAMA_PROBE_CACHE.clear()
    provider_module._SERVER_CAPS_CACHE.clear()
    yield
    provider_module._OLLAMA_PROBE_CACHE.clear()
    provider_module._SERVER_CAPS_CACHE.clear()


@pytest.fixture
def ollama_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaHandler)
    server.delay = 0.0  # type: ignore[attr-defined]
    server.caps = ["completion", "vision"]  # type: ignore[attr-defined]
    server.auth_headers = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _url(server: ThreadingHTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/v1"


def _free_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


def _settings(url: str, **overrides: object) -> Settings:
    base = Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="muse-spark-1.3",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
        local_model_url=url,
        local_model_name="qwen3:4b",
    )
    return replace(base, **overrides)


def _ticks_while(coro_factory) -> tuple[object, int]:
    """Run one async call and count heartbeat ticks inside it."""

    async def scenario():
        counter = [0]
        stop = asyncio.Event()

        async def heartbeat() -> None:
            while not stop.is_set():
                await asyncio.sleep(0.01)
                counter[0] += 1

        beat = asyncio.create_task(heartbeat())
        await asyncio.sleep(0.05)  # baseline
        before = counter[0]
        result = await coro_factory()
        during = counter[0] - before
        stop.set()
        await beat
        return result, during

    return asyncio.run(scenario())


def test_probe_and_caps_succeed_on_loopback(ollama_server) -> None:
    url = _url(ollama_server)
    provider = LocalEndpointProvider(
        _settings(url, local_model_name="uncurated:1b", local_model_vision=True)
    )

    async def scenario():
        detected = await probe_ollama_async(url)
        caps = await cached_server_caps_async(url, "uncurated:1b")
        return detected, caps, await provider.capabilities_async()

    detected, caps, declaration = asyncio.run(scenario())

    assert detected is True
    assert caps == ["completion", "vision"]
    # Unknown profile + explicit flag + server-advertised vision -> allowed.
    assert declaration.vision is True
    assert declaration.tool_calling is False
    assert declaration.processing_location == "local"
    # The probe populated the cache, so the sync accessor now agrees without
    # making another request.
    assert provider.capabilities().vision is True


def test_slow_probe_does_not_block_event_loop(ollama_server) -> None:
    ollama_server.delay = 0.4  # type: ignore[attr-defined]
    provider = LocalEndpointProvider(_settings(_url(ollama_server)))

    style, ticks = _ticks_while(provider.api_style_async)

    assert style == "ollama"
    # A blocking call would leave ~0 ticks during 400ms.
    assert ticks >= 5


def test_slow_caps_do_not_block_event_loop(ollama_server) -> None:
    ollama_server.delay = 0.3  # type: ignore[attr-defined]
    provider = LocalEndpointProvider(
        _settings(
            _url(ollama_server),
            local_model_name="uncurated:1b",
            local_model_vision=True,
        )
    )

    declaration, ticks = _ticks_while(provider.capabilities_async)

    assert declaration.vision is True
    assert ticks >= 5


def test_unreachable_endpoint_is_false_and_empty() -> None:
    url = f"http://127.0.0.1:{_free_port()}/v1"
    provider = LocalEndpointProvider(
        _settings(url, local_model_name="uncurated:1b", local_model_vision=True)
    )

    async def scenario():
        return (
            await probe_ollama_async(url),
            await cached_server_caps_async(url, "uncurated:1b"),
            await provider.capabilities_async(),
        )

    detected, caps, declaration = asyncio.run(scenario())

    assert detected is False
    assert caps == []
    assert declaration.vision is False


def test_sync_accessors_and_listing_never_probe(monkeypatch) -> None:
    def boom(*args: object, **kwargs: object) -> bool:
        raise AssertionError("synchronous probe must not run in sync paths")

    monkeypatch.setattr(provider_module, "probe_ollama", boom)
    monkeypatch.setattr(provider_module, "fetch_server_caps", boom)

    provider = LocalEndpointProvider(_settings("http://127.0.0.1:11434/v1"))

    # Unknown until an async probe runs; never a blocking request.
    assert provider.api_style() == "unresolved"
    assert provider.capabilities().vision is False

    monkeypatch.setenv("FIELDROOK_LOCAL_MODEL_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("FIELDROOK_LOCAL_MODEL_NAME", "qwen3:4b")
    monkeypatch.setenv("FIELDROOK_LOCAL_API", "auto")
    response = client.get("/api/providers")
    assert response.status_code == 200


def test_chat_resolves_style_without_sync_probe(ollama_server, monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_ollama_chat(self, base, model, messages, json_only, num_predict, timeout_s=None, cancel_scope=None):  # noqa: ANN001
        called["base"] = base
        return {"role": "assistant", "content": "ok"}

    def boom(*args: object, **kwargs: object) -> bool:
        raise AssertionError("chat must not call the sync probe")

    monkeypatch.setattr(provider_module.LocalEndpointProvider, "_ollama_chat", fake_ollama_chat)
    monkeypatch.setattr(provider_module, "probe_ollama", boom)

    provider = LocalEndpointProvider(_settings(_url(ollama_server), local_api="auto"))
    reply = asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))

    assert reply["content"] == "ok"
    assert str(called["base"]).startswith("http://127.0.0.1:")


def test_loop_capability_helper_prefers_async() -> None:
    from app.analysis.loop import _provider_capabilities

    class SyncOnly:
        def capabilities(self):
            return "sync"

    class Both:
        async def capabilities_async(self):
            return "async"

        def capabilities(self):
            return "sync"

    assert asyncio.run(_provider_capabilities(SyncOnly())) == "sync"
    assert asyncio.run(_provider_capabilities(Both())) == "async"

def _stub_connection_test(monkeypatch, ollama_server) -> None:
    """Route-level connection tests should not run real model completions."""
    from app.routers import investigations

    monkeypatch.setattr(
        investigations,
        "load_settings",
        lambda: _settings(
            _url(ollama_server),
            local_model_name="uncurated:1b",
            local_model_vision=True,
            local_api="auto",
        ),
    )

    async def fake_chat(
        self, base, model, messages, json_only, num_predict,
        timeout_s=None, cancel_scope=None,
    ):
        return {"role": "assistant", "content": "OK"}

    monkeypatch.setattr(LocalEndpointProvider, "_ollama_chat", fake_chat)


def test_explicit_connection_test_recovers_from_negative_probe(
    ollama_server, monkeypatch,
) -> None:
    url = _url(ollama_server)
    ollama_server.tags_enabled = False  # type: ignore[attr-defined]
    assert asyncio.run(probe_ollama_async(url)) is False

    ollama_server.tags_enabled = True  # type: ignore[attr-defined]
    # A normal background probe must still honor its negative TTL.
    assert asyncio.run(probe_ollama_async(url)) is False

    _stub_connection_test(monkeypatch, ollama_server)
    response = client.post("/api/providers/local/test")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["api_style"] == "ollama"
    assert payload["server_caps"] == ["completion", "vision"]


def test_explicit_connection_test_refreshes_stale_model_caps(
    ollama_server, monkeypatch,
) -> None:
    url = _url(ollama_server)
    _stub_connection_test(monkeypatch, ollama_server)

    ollama_server.caps = ["completion"]  # type: ignore[attr-defined]
    first = client.post("/api/providers/local/test")
    assert first.status_code == 200
    assert first.json()["server_caps"] == ["completion"]

    ollama_server.caps = ["completion", "vision"]  # type: ignore[attr-defined]
    # Background callers must continue to receive their cached value.
    assert asyncio.run(cached_server_caps_async(url, "uncurated:1b")) == [
        "completion"
    ]

    second = client.post("/api/providers/local/test")
    assert second.status_code == 200
    payload = second.json()
    assert payload["ok"] is True
    assert payload["server_caps"] == ["completion", "vision"]
    assert asyncio.run(cached_server_caps_async(url, "uncurated:1b")) == [
        "completion", "vision"
    ]


def test_preset_cancel_skips_auto_style_probe_in_chat_and_task(
    ollama_server,
) -> None:
    """Both direct local entry points honor pre-set flags before /api/tags."""
    from app.analysis.provider import RoundCancelled
    from app.investigations import persistence

    provider = LocalEndpointProvider(
        _settings(_url(ollama_server), local_api="auto")
    )
    operations = (
        ("m030-cancel-chat", lambda scope: provider.chat(
            [{"role": "user", "content": "hi"}], cancel_scope=scope
        )),
        ("m030-cancel-task", lambda scope: provider.run_task(
            "triage", "prompt", cancel_scope=scope
        )),
    )
    for inv_id, operation in operations:
        persistence.request_cancel(inv_id, 0)
        try:
            with pytest.raises(RoundCancelled):
                asyncio.run(operation((inv_id, 0)))
        finally:
            persistence.clear_cancel(inv_id)
    assert getattr(ollama_server, "tags_hits", 0) == 0


def test_preset_cancel_skips_cold_capability_probe(
    ollama_server,
) -> None:
    """A pre-existing flag must stop before any probe or model task."""
    from app.analysis.loop import _run_local_tasks
    from app.investigations import persistence
    from app.investigations.store import InvestigationState

    state = InvestigationState(
        id="m030-preset-caps",
        problem="Excel hangs",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "Excel hangs"}],
        target="remote",
    )
    provider = LocalEndpointProvider(
        _settings(_url(ollama_server), local_api="auto")
    )
    persistence.request_cancel(state.id, state.rounds_used)
    try:
        asyncio.run(_run_local_tasks(state, provider, provider._settings, False))
        assert getattr(ollama_server, "tags_hits", 0) == 0
        assert state.assessment is None
        assert any("cancelled" in w.lower() for w in state.warnings)
        assert persistence.cancel_requested(state.id, state.rounds_used) is False
    finally:
        persistence.clear_cancel(state.id)


@pytest.mark.parametrize("slow_path", ["tags", "show"])
def test_midflight_cancel_aborts_slow_capability_probe(
    ollama_server, monkeypatch, slow_path,
) -> None:
    """Cancel during slow /api/tags or /api/show without losing evidence."""
    import app.analysis.loop as loop_module
    from app.investigations import persistence
    from app.investigations.store import InvestigationState

    started = threading.Event()
    if slow_path == "tags":
        ollama_server.delay = 3.0  # type: ignore[attr-defined]
        ollama_server.tags_started = started  # type: ignore[attr-defined]
    else:
        ollama_server.show_delay = 3.0  # type: ignore[attr-defined]
        ollama_server.show_started = started  # type: ignore[attr-defined]
        assert asyncio.run(probe_ollama_async(_url(ollama_server))) is True
    state = InvestigationState(
        id=f"m030-midflight-{slow_path}-caps",
        problem="Excel hangs",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "Excel hangs"}],
        target="remote",
    )
    original = state.add_evidence(
        category="technician",
        source="technician",
        data={"observation": "Observed error code 123"},
    )
    provider = LocalEndpointProvider(
        _settings(_url(ollama_server), local_api="auto")
    )
    monkeypatch.setattr(
        loop_module, "select_provider",
        lambda settings, override: (provider, "live"),
    )

    async def scenario() -> float:
        cancelled_at: list[float] = []

        async def file_cancel() -> None:
            assert await asyncio.to_thread(started.wait, 4.0)
            persistence.request_cancel(state.id, 0)
            cancelled_at.append(time.monotonic())

        filer = asyncio.create_task(file_cancel())
        try:
            await asyncio.wait_for(
                loop_module.run_rounds(state, provider._settings), timeout=6.0
            )
        finally:
            await filer
        assert cancelled_at, "the test must request cancellation mid-probe"
        return time.monotonic() - cancelled_at[0]

    try:
        elapsed = asyncio.run(scenario())
        assert elapsed < 1.2, f"cancel took {elapsed:.2f}s after flag was set"
        assert state.rounds_used == 1
        assert state.assessment is None
        assert [item.id for item in state.evidence] == [original.id]
        assert any("cancelled" in w.lower() for w in state.warnings)
        assert not any(a.title == "Investigation complete" for a in state.activity)
        assert persistence.cancel_requested(state.id, 0) is False
    finally:
        persistence.clear_cancel(state.id)




# ---------------------------------------------------------------------------
# M030 D3/D5: honest provider listing and fail-closed probe boundaries
# ---------------------------------------------------------------------------


def test_unprobed_api_style_is_unresolved_and_listing_is_cache_only(monkeypatch) -> None:
    """Only an actual verdict or explicit override may name a transport."""
    from app.routers import investigations

    url = "http://127.0.0.1:11434/v1"
    model = "uncurated:1b"
    settings = _settings(url, local_model_name=model, local_api="auto")
    monkeypatch.setattr(investigations, "load_settings", lambda: settings)

    def no_sync_http(*args, **kwargs):
        raise AssertionError("provider listing must not contact a model server")

    monkeypatch.setattr(provider_module, "probe_ollama", no_sync_http)
    monkeypatch.setattr(provider_module, "fetch_server_caps", no_sync_http)

    provider = LocalEndpointProvider(settings)
    origin = provider_module._origin_of(url)

    def listed_style() -> str:
        response = client.get("/api/providers")
        assert response.status_code == 200
        local = next(item for item in response.json() if item["name"] == "local")
        return local["api_style"]

    assert provider.api_style() == "unresolved"
    assert listed_style() == "unresolved"

    provider_module._OLLAMA_PROBE_CACHE[origin] = (time.monotonic() + 60, True)
    assert provider.api_style() == "ollama"
    assert listed_style() == "ollama"

    provider_module._OLLAMA_PROBE_CACHE[origin] = (time.monotonic() + 60, False)
    assert provider.api_style() == "openai"
    assert listed_style() == "openai"

    provider_module._OLLAMA_PROBE_CACHE[origin] = (time.monotonic() - 1, True)
    assert provider.api_style() == "unresolved"
    assert listed_style() == "unresolved"

    for forced in ("openai", "ollama"):
        override = _settings(url, local_model_name=model, local_api=forced)
        monkeypatch.setattr(investigations, "load_settings", lambda s=override: s)
        assert LocalEndpointProvider(override).api_style() == forced
        assert listed_style() == forced


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://models.example.com/v1",
        "http://192.168.1.10:11434/v1",
        "http://127.0.0.1.evil.test:11434/v1",
        "http://localhost@evil.test:11434/v1",
    ],
)
def test_direct_probe_helpers_refuse_remote_host_without_http(
    raw_url, monkeypatch,
) -> None:
    """Private direct-entry helpers must not bypass the caller's loopback gate."""
    attempts = []

    class NoNetwork:
        def __init__(self, *args, **kwargs):
            attempts.append("constructed")
            raise AssertionError("HTTP client was created for a non-loopback URL")

    monkeypatch.setattr(provider_module.httpx, "Client", NoNetwork)
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", NoNetwork)

    assert provider_module.probe_ollama(raw_url) is False
    assert asyncio.run(probe_ollama_async(raw_url, refresh=True)) is False
    assert provider_module.fetch_server_caps(raw_url, "uncurated:1b") == []
    assert asyncio.run(
        provider_module.fetch_server_caps_async(raw_url, "uncurated:1b")
    ) == []
    assert attempts == []


def test_local_transports_never_forward_configured_cloud_api_key(
    ollama_server,
) -> None:
    """Local Ollama and OpenAI-style HTTP requests must send no bearer token."""
    url = _url(ollama_server)
    key = "cloud-api-key-must-not-leak"
    async def exercise() -> None:
        auto = LocalEndpointProvider(
            _settings(
                url, local_model_name="uncurated:1b",
                local_api="auto", model_api_key=key,
            )
        )
        assert (await auto.capabilities_async()).processing_location == "local"
        assert (await auto.chat([{"role": "user", "content": "ping"}]))["content"] == "OK"
        openai = LocalEndpointProvider(
            _settings(url, local_api="openai", model_api_key=key)
        )
        assert (await openai.chat([{"role": "user", "content": "ping"}]))["content"] == "OK"

    asyncio.run(exercise())
    seen = list(ollama_server.auth_headers)
    assert {path for path, _ in seen} >= {
        "/api/tags", "/api/show", "/api/chat", "/v1/chat/completions",
    }
    assert all(authorization is None for _, authorization in seen)
