"""M019 streaming transport + mid-flight cancel."""

import asyncio
import json
import time

import httpx
import pytest

from app.analysis.loop import run_rounds
from app.analysis.provider import (
    LocalEndpointProvider,
    RoundCancelled,
    _await_cancellable,
    _flag_set,
)
from app.config import Settings
from app.investigations import persistence
from app.investigations.store import InvestigationState


def _settings(**overrides) -> Settings:
    base = {
        "model_api_key": None,
        "model_base_url": "https://api.meta.ai/v1",
        "model_name": "muse-spark-1.3",
        "fixtures_mode": "always",
        "command_timeout_s": 5.0,
        "model_timeout_s": 5.0,
        "local_model_url": "http://127.0.0.1:11434/v1",
        "local_model_name": "qwen3:4b",
        "local_api": "ollama",
    }
    base.update(overrides)
    return Settings(**base)


# ---------------------------------------------------------------------------
# Cancel race helper
# ---------------------------------------------------------------------------


async def _slow(value: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return value


async def _boom() -> str:
    raise ValueError("inner failure")


def test_no_scope_awaits_normally() -> None:
    assert asyncio.run(_await_cancellable(_slow("ok", 0.01), None)) == "ok"


def test_inner_errors_propagate_not_cancel() -> None:
    with pytest.raises(ValueError, match="inner failure"):
        asyncio.run(_await_cancellable(_boom(), ("inv-x", 0)))


def test_preset_flag_aborts_before_start() -> None:
    persistence.request_cancel("inv-preset", 0)
    try:
        started = time.monotonic()
        with pytest.raises(RoundCancelled, match="before the model call started"):
            asyncio.run(_await_cancellable(_slow("never", 30.0), ("inv-preset", 0)))
        assert time.monotonic() - started < 5.0, "must not wait out the call"
    finally:
        persistence.clear_cancel("inv-preset")


def test_midflight_flag_aborts_the_wait() -> None:
    async def main() -> float:
        async def file_flag() -> None:
            await asyncio.sleep(0.1)
            persistence.request_cancel("inv-mid", 0)

        started = time.monotonic()
        filer = asyncio.ensure_future(file_flag())
        try:
            with pytest.raises(RoundCancelled, match="during the model call"):
                await _await_cancellable(_slow("never", 30.0), ("inv-mid", 0))
        finally:
            await filer
        return time.monotonic() - started

    try:
        elapsed = asyncio.run(main())
    finally:
        persistence.clear_cancel("inv-mid")
    assert elapsed < 5.0, f"cancel took {elapsed:.1f}s; the wait must abort promptly"


def test_flag_check_never_raises() -> None:
    assert _flag_set("inv-missing", 0) is False


# ---------------------------------------------------------------------------
# Ollama streaming transport (fake HTTP)
# ---------------------------------------------------------------------------


class _StreamScript:
    def __init__(self, lines, status=200, body=b"", on_line=None) -> None:
        self.lines = lines
        self.status = status
        self.body = body
        self.on_line = on_line


class _FakeStream:
    def __init__(self, script: _StreamScript) -> None:
        self._script = script

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    @property
    def status_code(self):
        return self._script.status

    async def aread(self) -> bytes:
        return self._script.body

    async def aiter_lines(self):
        for line in self._script.lines:
            if self._script.on_line is not None:
                self._script.on_line()
            yield line


class _FakeClient:
    script: _StreamScript | None = None
    posted: list = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def stream(self, method, url, json=None):
        _FakeClient.posted.append({"method": method, "url": url, "json": json})
        assert _FakeClient.script is not None, "test must set _FakeClient.script"
        return _FakeStream(_FakeClient.script)


def _ndjson(*events) -> list[str]:
    return [json.dumps(event) for event in events]


@pytest.fixture
def fake_http(monkeypatch):
    _FakeClient.posted = []
    _FakeClient.script = None
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return _FakeClient


def test_stream_assembles_completed_reply_only(fake_http) -> None:
    fake_http.script = _StreamScript(
        _ndjson(
            {"message": {"content": '{"a":'}, "done": False},
            {"message": {"content": " 1}"}, "done": False},
            {
                "message": {"content": ""},
                "done": True,
                "eval_count": 42,
                "eval_duration": 6_000_000_000,
                "prompt_eval_count": 120,
                "load_duration": 500_000_000,
            },
        )
    )
    provider = LocalEndpointProvider(_settings())
    reply = asyncio.run(
        provider._ollama_chat(
            "http://127.0.0.1:11434/v1", "qwen3:4b",
            [{"role": "user", "content": "hi"}], True, 220,
        )
    )
    assert reply == {"role": "assistant", "content": '{"a": 1}'}
    assert len(fake_http.posted) == 1
    payload = fake_http.posted[0]["json"]
    assert payload["stream"] is True
    assert payload["format"] == "json"
    stats = provider.last_stats
    assert stats["eval_count"] == 42
    assert stats["eval_duration_s"] == 6.0
    assert stats["first_token_s"] is not None
    assert stats["stream_chunks"] == 3


def test_stream_preset_flag_sends_no_http(fake_http) -> None:
    fake_http.script = _StreamScript([])
    persistence.request_cancel("inv-stream-preset", 0)
    try:
        provider = LocalEndpointProvider(_settings())
        with pytest.raises(RoundCancelled):
            asyncio.run(
                provider._ollama_chat(
                    "http://127.0.0.1:11434/v1", "qwen3:4b",
                    [{"role": "user", "content": "hi"}], True, 220,
                    cancel_scope=("inv-stream-preset", 0),
                )
            )
    finally:
        persistence.clear_cancel("inv-stream-preset")
    assert fake_http.posted == []


def test_stream_midflight_flag_aborts(fake_http) -> None:
    calls = {"n": 0}

    def file_on_second_line() -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            persistence.request_cancel("inv-stream-mid", 0)

    fake_http.script = _StreamScript(
        _ndjson(
            {"message": {"content": "part"}, "done": False},
            {"message": {"content": " ignored"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ),
        on_line=file_on_second_line,
    )
    try:
        provider = LocalEndpointProvider(_settings())
        with pytest.raises(RoundCancelled, match="during the model call"):
            asyncio.run(
                provider._ollama_chat(
                    "http://127.0.0.1:11434/v1", "qwen3:4b",
                    [{"role": "user", "content": "hi"}], True, 220,
                    cancel_scope=("inv-stream-mid", 0),
                )
            )
    finally:
        persistence.clear_cancel("inv-stream-mid")
    assert calls["n"] == 2, "abort must happen at the flag, not at stream end"


def test_stream_malformed_line_is_an_error(fake_http) -> None:
    fake_http.script = _StreamScript(["not json at all"])
    from app.analysis.validate import ModelAnalysisError

    provider = LocalEndpointProvider(_settings())
    with pytest.raises(ModelAnalysisError, match="malformed stream"):
        asyncio.run(
            provider._ollama_chat(
                "http://127.0.0.1:11434/v1", "qwen3:4b",
                [{"role": "user", "content": "hi"}], True, 220,
            )
        )


def test_stream_without_done_is_an_error(fake_http) -> None:
    fake_http.script = _StreamScript(
        _ndjson({"message": {"content": "partial"}, "done": False})
    )
    from app.analysis.validate import ModelAnalysisError

    provider = LocalEndpointProvider(_settings())
    with pytest.raises(ModelAnalysisError, match="without completion"):
        asyncio.run(
            provider._ollama_chat(
                "http://127.0.0.1:11434/v1", "qwen3:4b",
                [{"role": "user", "content": "hi"}], True, 220,
            )
        )


def test_stream_http_error_reports_status(fake_http) -> None:
    fake_http.script = _StreamScript([], status=500, body=b"boom")
    from app.analysis.validate import ModelAnalysisError

    provider = LocalEndpointProvider(_settings())
    with pytest.raises(ModelAnalysisError, match="HTTP 500"):
        asyncio.run(
            provider._ollama_chat(
                "http://127.0.0.1:11434/v1", "qwen3:4b",
                [{"role": "user", "content": "hi"}], True, 220,
            )
        )


def test_run_task_never_swallows_cancel_as_failure(fake_http) -> None:
    fake_http.script = _StreamScript([])
    persistence.request_cancel("inv-task-cancel", 0)
    try:
        provider = LocalEndpointProvider(_settings())
        with pytest.raises(RoundCancelled):
            asyncio.run(
                provider.run_task(
                    "triage", "prompt", cancel_scope=("inv-task-cancel", 0)
                )
            )
    finally:
        persistence.clear_cancel("inv-task-cancel")


# ---------------------------------------------------------------------------
# Loop-level cancel: stop the round, keep evidence, fabricate nothing
# ---------------------------------------------------------------------------


class _CancellingProvider:
    name = "local"

    def capabilities(self):
        from app.analysis.provider import ProviderCapabilities

        return ProviderCapabilities(
            text=True, vision=False, tool_calling=False,
            structured_output=False, processing_location="local",
        )

    def model_label(self) -> str:
        return "local/cancelling"

    async def run_task(self, task, prompt, timeout_s=None, images=None, cancel_scope=None):
        raise RoundCancelled("Round cancelled by the technician during the model call.")


def test_round_cancel_stops_without_fabrication(monkeypatch) -> None:
    import app.analysis.loop as loop_mod

    monkeypatch.setattr(
        loop_mod, "select_provider", lambda settings, override: (_CancellingProvider(), "live")
    )
    state = InvestigationState(
        id="inv-round-cancel",
        problem="Excel fails.",
        service_name=None,
        has_image=False,
        messages=[{"role": "user", "content": "Excel fails."}],
        target="remote",  # skip the host sweep; cancel must still stop the round
    )
    asyncio.run(run_rounds(state, _settings(), None, is_followup=False))
    assert state.rounds_used == 1
    assert state.assessment is None, "cancelled calls must not produce assessments"
    assert any("interrupted" in w or "cancelled" in w.lower() for w in state.warnings)
    assert any(r.title == "Round cancelled" for r in state.activity)
    assert not any(r.title == "Investigation complete" for r in state.activity)
    assert persistence.cancel_requested("inv-round-cancel", 1) is False
