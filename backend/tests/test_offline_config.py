"""Offline mode is a hard barrier against accidental live API calls."""
import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app import config
from app.analysis.provider import MetaModelProvider, select_provider
from app.analysis.validate import ModelAnalysisError
from app.main import app


def test_offline_beats_real_key_without_loading_dotenv(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "fake-live-key-not-real")
    monkeypatch.setenv("FIELDROOK_OFFLINE", "1")
    def unexpected_read(_path):
        raise AssertionError("offline mode must not read root .env")
    monkeypatch.setattr(config, "_load_dotenv_file", unexpected_read)
    settings = config.load_settings()
    assert settings.offline_mode is True
    assert settings.model_api_key is None
    _, mode = select_provider(settings)
    assert mode == "simulated"
    assert TestClient(app).get("/api/status").json()["model_mode"] == "simulated"


@pytest.mark.parametrize("flag", ["1", "true", "YES", "unexpected"])
def test_offline_true_values_are_fail_closed(monkeypatch, flag):
    monkeypatch.setenv("FIELDROOK_OFFLINE", flag)
    monkeypatch.setenv("MODEL_API_KEY", "fake-live-key-not-real")
    assert config.load_settings().model_api_key is None


@pytest.mark.parametrize("flag", ["0", "false", "off", "no"])
def test_explicit_false_allows_key(monkeypatch, flag):
    monkeypatch.setenv("FIELDROOK_OFFLINE", flag)
    monkeypatch.setenv("MODEL_API_KEY", "fake-live-key-not-real")
    assert config.load_settings().model_api_key == "fake-live-key-not-real"


def test_provider_blocks_http_even_if_key_was_injected(monkeypatch):
    monkeypatch.setenv("FIELDROOK_OFFLINE", "1")
    settings = replace(config.load_settings(), model_api_key="fake-live-key-not-real")
    async def attempt():
        await MetaModelProvider(settings).chat([{"role": "user", "content": "test"}])
    with pytest.raises(ModelAnalysisError, match="FIELDROOK_OFFLINE"):
        asyncio.run(attempt())


def test_explicit_offline_investigation_is_labeled(monkeypatch):
    monkeypatch.setenv("FIELDROOK_OFFLINE", "1")
    monkeypatch.setenv("MODEL_API_KEY", "fake-live-key-not-real")
    response = TestClient(app).post("/api/investigations", data={
        "problem": "Offline-safe test: service status", "use_fixtures": "true",
        "share_consent": "false",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_mode"] == "simulated"
    assert any("FIELDROOK_OFFLINE" in w for w in body["warnings"])
