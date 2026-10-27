"""M004 demo scenarios: phantom task (A), insufficient evidence (C)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _investigate(problem: str) -> dict:
    response = client.post("/api/investigations", data={"problem": problem})
    assert response.status_code == 200
    return response.json()


def test_scenario_a_phantom_task_investigation() -> None:
    body = _investigate("PowerShell windows keep flashing on the desktop every five minutes.")
    assert body["uses_fixtures"] is True
    tools = {record["tool_name"] for record in body["activity"] if record["tool_name"]}
    assert "get_scheduled_tasks" in tools
    task_items = [item for item in body["evidence"] if item["category"] == "scheduled_tasks"]
    assert task_items
    names = {task["task_name"] for task in task_items[0]["data"]["tasks"]}
    assert "FieldRookDemoPhantom" in names
    titles = [cause["title"] for cause in body["assessment"]["causes"]]
    assert any("cadence" in title for title in titles)
    joined = " ".join(body["assessment"]["uncertainties"])
    assert "FieldRookDemoPhantom" in joined
    assert "window-hiding" in joined
    assert "2147942667" in joined
    guidance = " ".join(body["assessment"]["next_actions"])
    assert "FieldRookDemoPhantom" in guidance
    assert "FieldRook cannot modify tasks" in guidance
    assert body["proposals"] == []  # diagnosis only; no corrective action exists for tasks
    assert body["assessment"]["mode"] == "simulated"


def test_scenario_a_stays_diagnosis_only_in_export() -> None:
    body = _investigate("PowerShell windows keep flashing on the desktop every five minutes.")
    report = client.get(f"/api/investigations/{body['investigation_id']}/export?format=markdown")
    assert report.status_code == 200
    assert "UNRESOLVED - investigated; no verified correction." in report.text
    assert "FieldRookDemoPhantom" in report.text


def test_scenario_c_insufficient_evidence_stays_honest() -> None:
    body = _investigate("My laptop freezes randomly every afternoon.")
    assert body["uses_fixtures"] is True
    tools = [record["tool_name"] for record in body["activity"] if record["tool_name"]]
    assert "get_os_info" in tools
    assert "search_event_logs" in tools
    assessment = body["assessment"]
    assert assessment["uncertainties"], "must state what is unknown"
    assert assessment["missing_evidence"], "must name missing evidence"
    assert assessment["next_actions"], "must recommend further diagnostics"
    assert body["proposals"] == [], "no fabricated certainty, no unsupported action"
    text = " ".join(
        [assessment["summary"], assessment["explanation"]]
        + [cause["title"] + cause["description"] for cause in assessment["causes"]]
    ).lower()
    assert "root cause" not in text or "cannot" in text or "unverified" in text
    report = client.get(f"/api/investigations/{body['investigation_id']}/export?format=markdown")
    assert "UNRESOLVED - investigated; no verified correction." in report.text


def test_scenario_c_followup_reuses_evidence() -> None:
    body = _investigate("My laptop freezes randomly every afternoon.")
    first_count = len(body["evidence"])
    followup = client.post(
        f"/api/investigations/{body['investigation_id']}/followup",
        json={"message": "Which observation supports that conclusion?"},
    )
    assert followup.status_code == 200
    again = followup.json()
    assert len(again["evidence"]) >= first_count
    assert any(record["title"] == "Follow-up received" for record in again["activity"])
    assert again["proposals"] == []
