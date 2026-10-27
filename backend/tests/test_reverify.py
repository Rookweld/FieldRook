"""M007 on-demand evidence reverification (fixture + simulated, no network)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200
    return response.json()


def test_reverify_unchanged_fixture_evidence() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    dns_items = [item for item in body["evidence"] if item["category"] == "dns_config"]
    assert dns_items
    old = dns_items[0]
    assert old["tool_name"] == "get_dns_config"

    response = client.post(
        f"/api/investigations/{body['investigation_id']}/reverify",
        json={"evidence_id": old["id"]},
    )
    assert response.status_code == 200
    again = response.json()

    # Historical evidence is never replaced: the old item is intact.
    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[old["id"]]["data"] == old["data"]
    assert by_id[old["id"]]["collected_at"] == old["collected_at"]

    assert len(again["refreshes"]) == 1
    refresh = again["refreshes"][0]
    assert refresh["old_evidence_id"] == old["id"]
    assert refresh["verdict"] == "unchanged"
    assert refresh["new_evidence_id"] in by_id
    assert by_id[refresh["new_evidence_id"]]["refresh_of"] == old["id"]
    assert refresh["compared_at"]
    assert refresh["old_collected_at"] == old["collected_at"]
    assert any(record["kind"] == "reverify" for record in again["activity"])


def test_reverify_detects_changed_service_state(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    body = _investigate(
        "Is the Windows Update service healthy?", service_name="wuauserv"
    )
    details = [item for item in body["evidence"] if item["category"] == "service_details"]
    assert details
    old = details[0]
    assert old["data"]["status"]["status"] == "Stopped"

    # The service changes state mid-investigation (synthetic fixture flip).
    monkeypatch.setenv("FIELDROOK_FIXTURE_SERVICE_STATES", "wuauserv=Running")
    response = client.post(
        f"/api/investigations/{body['investigation_id']}/reverify",
        json={"evidence_id": old["id"]},
    )
    assert response.status_code == 200
    again = response.json()
    assert len(again["refreshes"]) == 1
    refresh = again["refreshes"][0]
    assert refresh["verdict"] == "changed"
    assert any("status" in change for change in refresh["changes"])
    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[refresh["new_evidence_id"]]["data"]["status"]["status"] == "Running"
    # Historical item untouched.
    assert by_id[old["id"]]["data"]["status"]["status"] == "Stopped"
    assert any("differs from historical" in warning for warning in again["warnings"])


def test_reverify_reports_unavailable_when_collection_fails(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    body = _investigate(
        "Is the Windows Update service healthy?", service_name="wuauserv"
    )
    details = [item for item in body["evidence"] if item["category"] == "service_details"]
    assert details
    old = details[0]

    monkeypatch.setenv("FIELDROOK_FIXTURE_MISSING_SERVICES", "wuauserv")
    response = client.post(
        f"/api/investigations/{body['investigation_id']}/reverify",
        json={"evidence_id": old["id"]},
    )
    assert response.status_code == 200
    again = response.json()
    refresh = again["refreshes"][0]
    assert refresh["verdict"] == "unavailable"
    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[refresh["new_evidence_id"]]["error"] is not None
    assert by_id[old["id"]]["error"] is None
    assert any("failed to collect" in warning for warning in again["warnings"])


def test_reverify_names_affected_hypotheses(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    body = _investigate("Excel closes when I open a particular workbook.")
    crashes = [item for item in body["evidence"] if item["category"] == "app_crashes"]
    assert crashes
    old = crashes[0]
    titles_before = [cause["title"] for cause in body["assessment"]["causes"]]
    assert any("EXCEL.EXE" in title for title in titles_before)

    monkeypatch.setenv("FIELDROOK_FIXTURE_CRASH_EXTRA", "OUTLOOK.EXE")
    again = client.post(
        f"/api/investigations/{body['investigation_id']}/reverify",
        json={"evidence_id": old["id"]},
    ).json()
    refresh = again["refreshes"][0]
    assert refresh["verdict"] == "changed"
    assert any("EXCEL.EXE" in title for title in refresh["affected_causes"])
    # The rebuilt simulated assessment cites the fresh reading too.
    known = {item["id"] for item in again["evidence"]}
    for fact in again["assessment"]["facts"]:
        assert set(fact["evidence_ids"]) <= known


def test_reverify_rejects_screenshot_evidence() -> None:
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
        b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = client.post(
        "/api/investigations",
        data={"problem": "Error dialog on boot.", "share_consent": "true"},
        files={"screenshot": ("error.png", png, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    shots = [item for item in body["evidence"] if item["category"] == "screenshot"]
    assert shots
    assert shots[0]["tool_name"] is None
    denied = client.post(
        f"/api/investigations/{body['investigation_id']}/reverify",
        json={"evidence_id": shots[0]["id"]},
    )
    assert denied.status_code == 422


def test_reverify_unknown_ids_404() -> None:
    body = _investigate("DNS does not resolve anything.")
    assert (
        client.post(
            "/api/investigations/inv-doesnotexist/reverify",
            json={"evidence_id": "ev-1"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/investigations/{body['investigation_id']}/reverify",
            json={"evidence_id": "ev-999"},
        ).status_code
        == 404
    )


def test_reverify_refused_when_budget_exhausted() -> None:
    from app.investigations import persistence
    from app.investigations.store import InvestigationState

    state = InvestigationState(
        id="inv-budget-test", problem="Budget probe.", service_name=None, has_image=False
    )
    state.tool_calls_made = 12
    state.add_evidence(
        category="dns_config",
        source="tool:get_dns_config:fixture",
        data={"summary": "x", "warnings": [], "count": 1},
        tool_name="get_dns_config",
        tool_args={},
    )
    persistence.save_state(state)
    response = client.post(
        "/api/investigations/inv-budget-test/reverify", json={"evidence_id": "ev-1"}
    )
    assert response.status_code == 409


def test_refresh_history_persists_across_reload() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    dns_items = [item for item in body["evidence"] if item["category"] == "dns_config"]
    again = client.post(
        f"/api/investigations/{body['investigation_id']}/reverify",
        json={"evidence_id": dns_items[0]["id"]},
    ).json()
    assert len(again["refreshes"]) == 1
    fetched = client.get(f"/api/investigations/{body['investigation_id']}").json()
    assert len(fetched["refreshes"]) == 1
    assert fetched["refreshes"][0]["verdict"] == "unchanged"
    assert fetched["refreshes"][0]["old_evidence_id"] == dns_items[0]["id"]
    by_id = {item["id"]: item for item in fetched["evidence"]}
    assert by_id[dns_items[0]["id"]]["tool_name"] == "get_dns_config"
    assert by_id[again["refreshes"][0]["new_evidence_id"]]["refresh_of"] == dns_items[0]["id"]
