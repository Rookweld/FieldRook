"""M033-A inventory: fail-closed URL checks and metadata-only behavior."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from eval import m033_inventory as inventory


@pytest.mark.parametrize(
    "url", [
        "https://ollama.example.com:11434",
        "http://192.168.1.11:11434",
        "http://127.0.0.1.evil.test:11434",
        "http://localhost@evil.test:11434",
        "file:///tmp/models",
        "http://127.0.0.1:11434/api/tags",
        "http://127.0.0.1:11434?redirect=https://evil.test",
        "http://127.0.0.1:11434#malicious",
        "http://127.0.0.1:999999",
    ],
)
def test_reject_nonloopback_or_unsafe_origin_before_network(monkeypatch, url):
    def forbid(*args, **kwargs):
        raise AssertionError("Network attempted before rejecting URL")

    monkeypatch.setattr(inventory, "_safe_opener", forbid)
    with pytest.raises(ValueError):
        inventory.collect_inventory(url)


@pytest.mark.parametrize(
    "url,expected", [
        ("http://127.0.0.1:11434/", "http://127.0.0.1:11434"),
        ("http://localhost:11434", "http://localhost:11434"),
        ("http://[::1]:11434", "http://[::1]:11434"),
    ],
)
def test_valid_loopback_origins(url, expected):
    assert inventory.validated_origin(url) == expected


def test_allowed_metadata_routes_only(monkeypatch):
    seen = []

    class FakeResponse:
        def __init__(self, data):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self, size):
            return self.data[:size]

    def fake_urlopen(req, timeout):
        assert timeout == 6
        path = req.full_url.split(":11434", 1)[1]
        seen.append((path, req.get_method(), req.data))
        if path == "/api/tags":
            return FakeResponse(json.dumps({"models": [
                {"name": "qwen3:4b", "size": 2500000000, "details": {"parameter_size": "4.0B"}},
                {"name": "qwen3-vl:8b", "size": 6100000000},
                {"name": "mystery:latest", "size": 100},
            ]}).encode())
        if path == "/api/ps":
            return FakeResponse(b'{"models":[]}')
        if path == "/api/show":
            name = json.loads(req.data)["model"]
            return FakeResponse(json.dumps({"capabilities": [
                "completion", "vision"
            ] if name == "qwen3-vl:8b" else ["completion"]}).encode())
        raise AssertionError(f"Unexpected network endpoint {path}")

    class FakeOpener:
        def open(self, req, timeout):
            return fake_urlopen(req, timeout)

    monkeypatch.setattr(inventory, "_safe_opener", lambda: FakeOpener())
    result = inventory.collect_inventory("http://127.0.0.1:11434", observed_at="2026-11-17T00:00:00Z")
    assert result["schema_version"] == "m033-a.1"
    assert result["installed_count"] == 3
    assert len(seen) == 5
    assert [(p, method) for p, method, _ in seen] == [
        ("/api/tags", "GET"), ("/api/ps", "GET"),
        ("/api/show", "POST"), ("/api/show", "POST"), ("/api/show", "POST"),
    ]
    a, b, c = result["models"]
    assert a["curated_profile"] is True
    assert a["running_now"] is False
    assert a["possible_vision"] is False
    assert b["possible_vision"] is True
    assert c["curated_profile"] is False
    assert c["profile_performance_class"] == "unknown"


def test_unknown_active_status_when_ps_fails(monkeypatch):
    def fake_request(origin, route, payload=None):
        if route == "/api/tags":
            return {"models": [{"name": "qwen3:4b"}]}
        if route == "/api/ps":
            raise OSError("Unavailable")
        return {"capabilities": ["completion"]}

    monkeypatch.setattr(inventory, "_request_json", fake_request)
    report = inventory.collect_inventory("http://localhost:11434")
    assert report["models"][0]["running_now"] is None
    assert any("/api/ps unavailable" in w for w in report["warnings"])


def test_failed_show_is_unknown_not_guess_vision(monkeypatch):
    def fake_request(origin, route, payload=None):
        if route == "/api/tags":
            return {"models": [{"name": "qwen3-vl:8b"}]}
        if route == "/api/ps":
            return {"models": []}
        raise urllib.error.URLError("unavailable")

    monkeypatch.setattr(inventory, "_request_json", fake_request)
    report = inventory.collect_inventory("http://localhost:11434")
    model = report["models"][0]
    assert model["capabilities_observed"] is False
    assert model["possible_vision"] is False
    assert any("qwen3-vl:8b: /api/show failed" in w for w in report["warnings"])


@pytest.mark.parametrize("payload", [{"error": "bad"}, {"models": None}, {"models": {}}])
def test_tags_missing_models_fails_closed(monkeypatch, payload):
    monkeypatch.setattr(inventory, "_request_json", lambda *a, **kw: payload)
    with pytest.raises(ValueError, match="models array"):
        inventory.collect_inventory("http://127.0.0.1:11434")


def test_metadata_request_never_allows_generation(monkeypatch):
    monkeypatch.setattr(inventory, "_safe_opener", lambda *a, **kw: pytest.fail("Network not allowed"))
    with pytest.raises(ValueError, match="metadata"):
        inventory._request_json("http://127.0.0.1:11434", "/api/generate")
    with pytest.raises(ValueError, match="metadata"):
        inventory._request_json("http://127.0.0.1:11434", "/api/chat", {"model": "x"})
    with pytest.raises(ValueError, match="required"):
        inventory._request_json("http://127.0.0.1:11434", "/api/show", {})


def test_related_model_names_do_not_inherit_curated_quality(monkeypatch):
    """4B benchmark results must not be assigned to an unmeasured 8B variant."""
    def metadata(origin, route, payload=None):
        if route == "/api/tags":
            return {"models": [{"name": "qwen3:8b"}, {"name": "qwen3-vl:2b"}]}
        if route == "/api/ps":
            return {"models": []}
        return {"capabilities": ["completion", "tools", "vision"]}

    monkeypatch.setattr(inventory, "_request_json", metadata)
    models = inventory.collect_inventory("http://127.0.0.1:11434")["models"]
    assert len(models) == 2
    assert all(m["curated_profile"] is False for m in models)
    assert all(m["profile_performance_class"] == "unknown" for m in models)
    # Advertised capabilities alone do not grant screenshot permission.
    assert models[0]["possible_vision"] is True
    assert models[0]["workstation_only"] is None


def test_refuses_redirects_and_ignores_environment_proxies():
    opener = inventory._safe_opener()
    proxy_handlers = [h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler)]
    redirect_handlers = [h for h in opener.handlers if isinstance(h, inventory._RejectRedirects)]
    # urllib omits a supplied ProxyHandler({}) from the handler list; either
    # no proxy handler or an explicitly empty one is the safe result.
    assert all(handler.proxies == {} for handler in proxy_handlers)
    assert len(redirect_handlers) == 1
    with pytest.raises(ValueError, match="redirects"):
        redirect_handlers[0].redirect_request(
            None, None, 302, "Found", {},
            "https://example.com/model-data",
        )
