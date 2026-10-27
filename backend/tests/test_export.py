"""Incident export: Markdown ticket reports and structured JSON."""

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _investigation_id() -> str:
    response = client.post("/api/investigations", data={"problem": "Export probe problem."})
    assert response.status_code == 200
    return response.json()["investigation_id"]


def test_markdown_export_has_all_sections() -> None:
    inv_id = _investigation_id()
    response = client.get(f"/api/investigations/{inv_id}/export?format=markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    body = response.text
    for section in range(1, 12):
        assert f"## {section}." in body
    assert inv_id in body
    assert "Export probe problem." in body
    assert "data:image" not in body


def test_json_export_is_structured() -> None:
    inv_id = _investigation_id()
    response = client.get(f"/api/investigations/{inv_id}/export?format=json")
    assert response.status_code == 200
    data = json.loads(response.text)
    assert data["investigation_id"] == inv_id
    assert "evidence" in data and "activity" in data
    assert "proposals" in data and "executions" in data
    assert "notes" in data
    assert "next_steps" in data["assessment"]
    assert data["assessment"]["next_steps"]
    assert "exported_at" in data


def test_export_rejects_bad_format_and_unknown_id() -> None:
    inv_id = _investigation_id()
    assert client.get(f"/api/investigations/{inv_id}/export?format=pdf").status_code == 400
    assert client.get("/api/investigations/inv-nope/export").status_code == 404
