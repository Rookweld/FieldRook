"""API end-to-end checks in fixture mode (no network, no credentials)."""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_status_reports_simulated_mode_without_key() -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["model_mode"] == "simulated"
    assert body["fixtures_available"] is True
    assert body["service"] == "fieldrook-api"


def test_service_list_returns_fixtures() -> None:
    response = client.get("/api/services")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fixture"
    names = {service["name"] for service in body["services"]}
    assert "wuauserv" in names


def test_diagnostics_endpoint_returns_validated_bundle() -> None:
    response = client.get("/api/services/wuauserv/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fixture"
    assert [item["category"] for item in body["items"]] == [
        "service_status",
        "startup_type",
        "event_log",
    ]


def test_diagnostics_rejects_invalid_service_name() -> None:
    response = client.get("/api/services/bad;name/diagnostics")
    assert response.status_code == 400


def test_analyze_rejects_invalid_service_name() -> None:
    response = client.post("/api/incidents/analyze", json={"service_name": "bad;name"})
    assert response.status_code == 400


def test_analyze_end_to_end_fixture_and_simulated() -> None:
    response = client.post("/api/incidents/analyze", json={"service_name": "wuauserv"})
    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"]["mode"] == "fixture"
    assert body["analysis"]["mode"] == "simulated"
    assert body["analysis"]["facts"]
    known = {item["id"] for item in body["diagnostics"]["items"]}
    for fact in body["analysis"]["facts"]:
        assert set(fact["evidence_ids"]) <= known
    assert any("MODEL_API_KEY" in warning for warning in body["warnings"])


def test_no_system_modifying_routes_exposed() -> None:
    mutating = {"PUT", "PATCH", "DELETE"}
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = set(route.methods or set())
            assert not (methods & mutating), route.path
            if "POST" in methods:
                assert route.path == "/api/incidents/analyze"
