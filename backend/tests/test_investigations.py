"""Natural-language investigations end to end (fixture + simulated, no network)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG_MIN = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 20 + b"\xff\xd9"

NETWORK_PROBLEM = "My VPN disconnects every 10 minutes. Windows says the network adapter is unavailable."


def test_start_network_investigation_simulated() -> None:
    response = client.post("/api/investigations", data={"problem": NETWORK_PROBLEM})
    assert response.status_code == 200
    body = response.json()
    assert body["investigation_id"].startswith("inv-")
    assert body["uses_fixtures"] is True
    assert body["analysis_mode"] == "simulated"
    assert len(body["evidence"]) >= 3
    kinds = [record["kind"] for record in body["activity"]]
    for expected in ("plan", "tool_request", "tool_result", "evidence", "done"):
        assert expected in kinds
    tools_used = {record["tool_name"] for record in body["activity"] if record["tool_name"]}
    assert "get_network_adapters" in tools_used
    assert body["assessment"] is not None
    assert body["assessment"]["mode"] == "simulated"
    known = {item["id"] for item in body["evidence"]}
    for fact in body["assessment"]["facts"]:
        assert set(fact["evidence_ids"]) <= known
    assert any("MODEL_API_KEY" in warning for warning in body["warnings"])


def test_service_selection_is_optional() -> None:
    response = client.post("/api/investigations", data={"problem": "Something is slow."})
    assert response.status_code == 200
    assert response.json()["service_name"] is None


def test_invalid_service_name_rejected() -> None:
    response = client.post(
        "/api/investigations", data={"problem": "x", "service_name": "bad;name"}
    )
    assert response.status_code == 400


def test_empty_problem_rejected() -> None:
    response = client.post("/api/investigations", data={"problem": ""})
    assert response.status_code == 422


def test_screenshot_with_consent_accepted() -> None:
    response = client.post(
        "/api/investigations",
        data={"problem": "Error dialog on boot.", "share_consent": "true"},
        files={"screenshot": ("error.png", PNG_1X1, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_screenshot"] is True
    assert any("Screenshot" in warning for warning in body["warnings"])


def test_screenshot_without_consent_rejected() -> None:
    response = client.post(
        "/api/investigations",
        data={"problem": "Error dialog on boot."},
        files={"screenshot": ("error.png", PNG_1X1, "image/png")},
    )
    assert response.status_code == 400


def test_screenshot_bad_signature_rejected() -> None:
    response = client.post(
        "/api/investigations",
        data={"problem": "Error dialog.", "share_consent": "true"},
        files={"screenshot": ("error.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400


def test_screenshot_wrong_extension_rejected() -> None:
    response = client.post(
        "/api/investigations",
        data={"problem": "Error dialog.", "share_consent": "true"},
        files={"screenshot": ("error.txt", PNG_1X1, "image/png")},
    )
    assert response.status_code == 400


def test_screenshot_oversize_rejected() -> None:
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)
    response = client.post(
        "/api/investigations",
        data={"problem": "Error dialog.", "share_consent": "true"},
        files={"screenshot": ("big.png", big, "image/png")},
    )
    assert response.status_code == 400


def test_followup_continuity_reuses_evidence() -> None:
    started = client.post("/api/investigations", data={"problem": NETWORK_PROBLEM}).json()
    investigation_id = started["investigation_id"]
    first_ids = [item["id"] for item in started["evidence"]]
    first_activity = len(started["activity"])
    response = client.post(
        f"/api/investigations/{investigation_id}/followup",
        json={"message": "Check whether the network adapter recently disconnected."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["investigation_id"] == investigation_id
    assert len(body["activity"]) > first_activity
    continued_ids = [item["id"] for item in body["evidence"]]
    assert continued_ids[: len(first_ids)] == first_ids
    assert body["assessment"] is not None


def test_followup_unknown_id_404() -> None:
    response = client.post(
        "/api/investigations/inv-doesnotexist/followup", json={"message": "hello"}
    )
    assert response.status_code == 404


def test_followup_empty_message_rejected() -> None:
    started = client.post("/api/investigations", data={"problem": NETWORK_PROBLEM}).json()
    response = client.post(
        f"/api/investigations/{started['investigation_id']}/followup",
        json={"message": ""},
    )
    assert response.status_code == 422


def test_api_failure_substituted_gracefully(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app import config as config_module
    from app.analysis.provider import MetaModelProvider
    from app.analysis.validate import ModelAnalysisError
    from app.config import Settings
    from app.routers import investigations as inv_router

    real_load = config_module.load_settings

    def fake_load() -> Settings:
        current = real_load()
        return Settings(
            model_api_key="test-key-not-real",
            model_base_url=current.model_base_url,
            model_name=current.model_name,
            fixtures_mode="always",
            command_timeout_s=current.command_timeout_s,
            model_timeout_s=current.model_timeout_s,
        )

    async def boom(self, messages, tools=None, json_only=False):  # noqa: ANN001, ANN002, ANN003
        raise ModelAnalysisError("simulated outage")

    monkeypatch.setattr(inv_router, "load_settings", fake_load)
    monkeypatch.setattr(MetaModelProvider, "chat", boom)
    response = client.post("/api/investigations", data={"problem": NETWORK_PROBLEM})
    assert response.status_code == 200
    body = response.json()
    assert body["assessment"]["mode"] == "simulated"
    assert any("simulated outage" in warning for warning in body["warnings"])


def test_tools_endpoint_lists_registry() -> None:
    response = client.get("/api/tools")
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()}
    assert len(names) == 11
    assert {"get_dns_config", "search_event_logs", "get_scheduled_tasks"} <= names


def test_demo_worker_problem_uses_health_tool() -> None:
    body = client.post(
        "/api/investigations",
        data={"problem": "The FieldRook demo worker is down."},
    ).json()
    tools_used = {record["tool_name"] for record in body["activity"] if record["tool_name"]}
    assert "get_demo_worker_health" in tools_used


def test_failing_fixture_worker_creates_proposal(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    body = client.post(
        "/api/investigations",
        data={"problem": "The FieldRook demo worker is down."},
    ).json()
    assert len(body["proposals"]) == 1
    proposal = body["proposals"][0]
    assert proposal["action_id"] == "recover_demo_worker"
    assert proposal["target"] == "demo-worker"
    assert proposal["status"] == "AWAITING_APPROVAL"


def test_healthy_fixture_worker_creates_no_proposal() -> None:
    body = client.post(
        "/api/investigations",
        data={"problem": "The FieldRook demo worker is down."},
    ).json()
    assert body["proposals"] == []


def test_powershell_popup_problem_uses_task_tool() -> None:
    body = client.post(
        "/api/investigations",
        data={"problem": "Random PowerShell windows flash on the desktop every few minutes."},
    ).json()
    tools_used = {record["tool_name"] for record in body["activity"] if record["tool_name"]}
    assert "get_scheduled_tasks" in tools_used
    assert body["assessment"]["mode"] == "simulated"


def test_multi_step_activity_is_ordered() -> None:
    body = client.post("/api/investigations", data={"problem": NETWORK_PROBLEM}).json()
    seqs = [record["seq"] for record in body["activity"]]
    assert seqs == sorted(seqs)
    tool_results = [r for r in body["activity"] if r["kind"] == "tool_result"]
    assert len(tool_results) >= 2
