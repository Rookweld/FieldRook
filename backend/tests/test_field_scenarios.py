"""M007 field scenarios: four end-to-end active-investigation cases.

All state changes are synthetic fixture flips; no real Windows service,
network, task, or application is touched.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200
    return response.json()


def _reverify(investigation_id: str, evidence_id: str) -> dict:
    response = client.post(
        f"/api/investigations/{investigation_id}/reverify",
        json={"evidence_id": evidence_id},
    )
    assert response.status_code == 200
    return response.json()


def _by_category(body: dict, category: str) -> list[dict]:
    return [item for item in body["evidence"] if item["category"] == category]


def test_field_service_changes_state_during_investigation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Case 1: wuauserv is Stopped at intake, Running minutes later."""
    body = _investigate(
        "The Windows Update service looks wrong; is it healthy?", service_name="wuauserv"
    )
    old = _by_category(body, "service_details")[0]
    assert old["data"]["status"]["status"] == "Stopped"

    monkeypatch.setenv("FIELDROOK_FIXTURE_SERVICE_STATES", "wuauserv=Running")
    again = _reverify(body["investigation_id"], old["id"])
    refresh = again["refreshes"][0]
    assert refresh["verdict"] == "changed"
    assert refresh["old_evidence_id"] == old["id"]
    by_id = {item["id"]: item for item in again["evidence"]}
    # Both readings coexist: historical Stopped, current Running.
    assert by_id[old["id"]]["data"]["status"]["status"] == "Stopped"
    assert by_id[refresh["new_evidence_id"]]["data"]["status"]["status"] == "Running"
    assert by_id[refresh["new_evidence_id"]]["refresh_of"] == old["id"]


def test_field_network_contradiction_resolves_honestly() -> None:
    """Case 2: the user insists the network is down; adapters measure Up."""
    body = _investigate(
        "The network is down on this machine, I am sure the cable is unplugged."
    )
    assert len(body["contradictions"]) == 1
    assert body["suggested_rechecks"], "contradiction must suggest a targeted re-check"

    # The technician re-checks the disputed reading; it has not changed.
    adapters = _by_category(body, "net_adapters")[0]
    again = _reverify(body["investigation_id"], adapters["id"])
    assert again["refreshes"][0]["verdict"] == "unchanged"
    # The contradiction stands on two agreeing readings: the honest output is
    # "measurement disagrees with the report", not a fabricated outage cause.
    assert len(again["contradictions"]) == 1
    assert again["proposals"] == []
    assert again["assessment"]["uncertainties"]


def test_field_new_crash_redirects_leading_hypothesis(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Case 3: a fresh crash record moves the leading hypothesis."""
    body = _investigate("Excel and Outlook keep crashing this morning.")
    before = [cause["title"] for cause in body["assessment"]["causes"]]
    assert before[0] == "Crash evidence names EXCEL.EXE"

    monkeypatch.setenv("FIELDROOK_FIXTURE_CRASH_EXTRA", "OUTLOOK.EXE")
    old = _by_category(body, "app_crashes")[0]
    again = _reverify(body["investigation_id"], old["id"])
    assert again["refreshes"][0]["verdict"] == "changed"
    after = [cause["title"] for cause in again["assessment"]["causes"]]
    assert after[0] == "Crash evidence names OUTLOOK.EXE"
    assert any("EXCEL.EXE" in title for title in again["refreshes"][0]["affected_causes"])
    # The superseded hypothesis is named, not silently dropped: its evidence
    # is still in the record.
    assert any("EXCEL" in fact["statement"] for fact in again["assessment"]["facts"])


def test_field_unresolved_stays_unresolved_after_empty_recheck() -> None:
    """Case 4: re-checking an honest dead end yields nothing new."""
    body = _investigate("My laptop freezes randomly every afternoon.")
    assert body["assessment"]["uncertainties"]
    assert body["suggested_rechecks"] == []

    os_info = _by_category(body, "os_info")[0]
    again = _reverify(body["investigation_id"], os_info["id"])
    assert again["refreshes"][0]["verdict"] == "unchanged"
    assert again["proposals"] == []
    assert again["assessment"]["uncertainties"]
    assert again["assessment"]["missing_evidence"]
    report = client.get(
        f"/api/investigations/{body['investigation_id']}/export?format=markdown"
    )
    assert report.status_code == 200
    assert "UNRESOLVED - investigated; no verified correction." in report.text
    assert "Evidence refresh history" in report.text
