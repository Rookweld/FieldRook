"""FORGE lead step 1: target identity, collector packages, citations.

Round-trip through the assist JSON doc (no migration), export sections,
and backward compatibility with pre-FORGE rows.
"""

import json
import os
import sqlite3

from fastapi.testclient import TestClient

from app.investigations import persistence
from app.investigations.store import store
from app.main import app
from app.schemas import CitationRecord, CollectorPackageRecord, TargetIdentity

client = TestClient(app)


def _db_path() -> str:
    path = os.environ.get("FIELDROOK_DB_PATH", "")
    assert path, "conftest must isolate FIELDROOK_DB_PATH"
    return path


def test_forge_fields_round_trip() -> None:
    state = store.create(problem="FORGE probe.", service_name=None, has_image=False)
    state.target_identity = TargetIdentity(hostname_hash="ab" * 32, hint="front-desk-pc")
    state.collector_packages = [
        CollectorPackageRecord(
            package_id="pkg-1",
            collector_version="0.1.0",
            manifest_sha256="cd" * 32,
            evidence_ids=["ev-1"],
            warnings=["clock skew suspected"],
        )
    ]
    state.citations = [
        CitationRecord(kind="reference", ref_id="dns-triage", title="DNS triage",
                       locator="dns-triage.md#flush", rank="COMMUNITY"),
        CitationRecord(kind="case", ref_id="kb-1", title="Prior fix",
                       locator="kb-1", rank="TECH_CONFIRMED"),
    ]
    store.save(state)
    loaded = store.get(state.id)
    assert loaded is not None
    assert loaded.target_identity is not None
    assert loaded.target_identity.hostname_hash == "ab" * 32
    assert loaded.target_identity.hint == "front-desk-pc"
    assert len(loaded.collector_packages) == 1
    assert loaded.collector_packages[0].package_id == "pkg-1"
    assert loaded.collector_packages[0].evidence_ids == ["ev-1"]
    assert [c.ref_id for c in loaded.citations] == ["dns-triage", "kb-1"]
    response = loaded.to_response(uses_fixtures=True)
    assert response.target_identity is not None
    assert len(response.collector_packages) == 1
    assert len(response.citations) == 2


def test_pre_forge_rows_load_with_defaults() -> None:
    state = store.create(problem="Legacy probe.", service_name=None, has_image=False)
    store.save(state)
    # Simulate a pre-FORGE assist doc by stripping the new keys.
    conn = sqlite3.connect(_db_path())
    try:
        row = conn.execute(
            "SELECT doc_json FROM assist WHERE inv_id = ?", (state.id,)
        ).fetchone()
        doc = json.loads(row[0])
        for key in ("target_identity", "collector_packages", "citations"):
            doc.pop(key, None)
        conn.execute(
            "UPDATE assist SET doc_json = ? WHERE inv_id = ?",
            (json.dumps(doc), state.id),
        )
        conn.commit()
    finally:
        conn.close()
    loaded = store.get(state.id)
    assert loaded is not None
    assert loaded.target_identity is None
    assert loaded.collector_packages == []
    assert loaded.citations == []
    # Re-saving backfills the keys without crashing.
    store.save(loaded)
    again = store.get(state.id)
    assert again is not None and again.collector_packages == []


def test_export_carries_forge_sections() -> None:
    response = client.post("/api/investigations", data={"problem": "FORGE export probe."})
    assert response.status_code == 200
    inv_id = response.json()["investigation_id"]
    payload = response.json()
    assert payload["target_identity"] is None
    assert payload["collector_packages"] == []
    assert payload["citations"] == []
    exported = client.get(f"/api/investigations/{inv_id}/export?format=json")
    assert exported.status_code == 200
    data = json.loads(exported.text)
    assert data["exporter_version"] == "1.1"
    assert "collector_packages" in data and "citations" in data
    md = client.get(f"/api/investigations/{inv_id}/export?format=markdown")
    assert md.status_code == 200
    assert "## 18. Collector package provenance" in md.text
    assert "## 19. Citations" in md.text
    assert "(no collector packages imported)" in md.text
