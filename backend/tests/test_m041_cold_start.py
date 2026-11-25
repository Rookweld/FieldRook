"""M041 deadline and recovery tests. Delays are mocked; no GPU or network required."""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.analysis.provider import LocalEndpointProvider, RoundCancelled
from app.analysis.validate import ModelAnalysisError
from app.config import Settings


def provider() -> LocalEndpointProvider:
    return LocalEndpointProvider(Settings(
        model_api_key=None, model_base_url='https://api.meta.ai/v1',
        model_name='muse-spark-1.3', fixtures_mode='never',
        command_timeout_s=5.0,
        local_model_url="http://127.0.0.1:11434/v1",
        local_model_name="qwen3:4b",
        local_api="ollama",
        model_timeout_s=5.0,
    ))


TRIAGE = (
    '{"question":"Check the local error log?",'
    '"why":"Find first startup blocker","hypotheses":[],'
    '"next_check":"Read the startup stderr.","unknowns":[]}'
)
PLAN = '{"steps":[]}'


def test_transient_cold_start_timeout_recovers_once(monkeypatch) -> None:
    p = provider()
    calls = []

    async def fake(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            # This stalls beyond the first attempt's reserved fraction.
            await asyncio.sleep(0.3)
        return {"content": TRIAGE}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    t0 = time.perf_counter()
    result, warnings = asyncio.run(p.run_task("triage", "case", timeout_s=0.24))
    elapsed = time.perf_counter() - t0
    assert result is not None and result["question"] == "Check the local error log?", f"warnings={warnings}, stats={p.last_stats}, calls={len(calls)}"
    assert len(calls) == 2
    assert elapsed < 0.4
    assert p.last_stats["status"] == "model"
    assert p.last_stats["attempts"] == 2
    assert p.last_stats["retry_used"] is True
    assert any("recovered" in w for w in warnings)
    assert not any("fallback" in w for w in warnings)


def test_two_timeouts_have_one_hard_total_budget_and_fallback(monkeypatch) -> None:
    p = provider()
    calls = []

    async def fake(*args, **kwargs):
        calls.append(1)
        await asyncio.sleep(5)
        return {"content": TRIAGE}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    t0 = time.perf_counter()
    result, warnings = asyncio.run(p.run_task("triage", "case", timeout_s=0.24))
    elapsed = time.perf_counter() - t0
    assert result is None
    assert len(calls) == 2
    assert elapsed < 0.45, elapsed
    assert p.last_stats["status"] == "failed"
    assert p.last_stats["failure_kind"] in ("timeout", "deadline")
    assert any("deterministic fallback" in w for w in warnings)
    assert any("no model reasoning" in w for w in warnings)


def test_non_timeout_model_error_is_not_retried(monkeypatch) -> None:
    p = provider()
    count = 0

    async def fake(*args, **kwargs):
        nonlocal count
        count += 1
        raise ModelAnalysisError("Local model HTTP 400: invalid model name")

    monkeypatch.setattr(p, "_ollama_chat", fake)
    result, warnings = asyncio.run(p.run_task("triage", "case", timeout_s=0.4))
    assert result is None and count == 1
    assert p.last_stats["attempts"] == 1
    assert p.last_stats["retry_used"] is False
    assert p.last_stats["failure_kind"] == "model_error"
    assert any("fallback" in w for w in warnings)


def test_httpx_readtimeout_cause_is_retryable(monkeypatch) -> None:
    p = provider()
    count = 0

    async def fake(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            try:
                raise httpx.ReadTimeout("waiting for local Ollama")
            except httpx.ReadTimeout as exc:
                raise ModelAnalysisError("Local model request failed (ReadTimeout)") from exc
        return {"content": TRIAGE}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    result, warnings = asyncio.run(p.run_task("triage", "case", timeout_s=0.8))
    assert count == 2
    assert result is not None
    assert p.last_stats["attempts"] == 2
    assert any("retry" in w for w in warnings)


def test_reassess_does_not_duplicate_slow_model_calls(monkeypatch) -> None:
    p = provider()
    count = 0

    async def fake(*args, **kwargs):
        nonlocal count
        count += 1
        await asyncio.sleep(1)
        return {"content": TRIAGE}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    result, warnings = asyncio.run(p.run_task("reassess", "case", timeout_s=0.18))
    assert result is None
    assert count == 1
    assert any("fallback" in w for w in warnings)


def test_json_repair_is_inside_same_wall_clock_budget(monkeypatch) -> None:
    p = provider()
    repairs = 0

    async def fake(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"content": "not json"}

    async def repair(*args, **kwargs):
        nonlocal repairs
        repairs += 1
        await asyncio.sleep(1)
        return {"steps": []}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    monkeypatch.setattr(p, "_repair_json", repair)
    started = time.perf_counter()
    result, warnings = asyncio.run(p.run_task("plan", "case", timeout_s=0.2))
    assert result is None and repairs == 1
    assert time.perf_counter() - started < 0.37
    assert p.last_stats["failure_kind"] == "invalid_json"
    assert any("repair exceeded" in w for w in warnings)
    assert any("no model reasoning" in w for w in warnings)


def test_successful_json_repair_remains_distinct_from_timeout_retry(monkeypatch) -> None:
    p = provider()
    count = 0

    async def fake(*args, **kwargs):
        nonlocal count
        count += 1
        return {"content": "oops"}

    async def repair(*args, **kwargs):
        return {"steps": []}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    monkeypatch.setattr(p, "_repair_json", repair)
    result, warnings = asyncio.run(p.run_task("plan", "case", timeout_s=0.6))
    assert result == {"steps": []}
    assert count == 1
    assert p.last_stats["attempts"] == 1
    assert p.last_stats["retry_used"] is False
    assert any("JSON repair retry" in w for w in warnings)


def test_cancellation_never_turns_into_timeout_fallback(monkeypatch) -> None:
    import app.analysis.provider as provider_module

    p = provider()
    monkeypatch.setattr(provider_module, "_flag_set", lambda *args: True)

    async def fake(*args, **kwargs):
        return {"content": TRIAGE}

    monkeypatch.setattr(p, "_ollama_chat", fake)
    with pytest.raises(RoundCancelled):
        asyncio.run(p.run_task(
            "triage", "case", timeout_s=0.3, cancel_scope=("inv-test", 1)
        ))


def test_prior_success_stats_are_not_reused_after_failure(monkeypatch) -> None:
    p = provider()
    p.last_stats = {
        "eval_count": 1000,
        "status": "model",
        "wall_s": 1,
    }

    async def fake(*args, **kwargs):
        raise ModelAnalysisError("HTTP 404: unknown model")

    monkeypatch.setattr(p, "_ollama_chat", fake)
    result, _warnings = asyncio.run(p.run_task("triage", "case", timeout_s=0.5))
    assert result is None
    assert p.last_stats["status"] == "failed"
    assert "eval_count" not in p.last_stats
