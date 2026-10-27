"""M009 technician's memory: library, matching, regression, management."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200
    return response.json()


def _resolve_worker(inv_id: str, evidence_id: str, monkeypatch=None, flip_to="healthy") -> dict:
    """Manual plan -> baseline -> claim -> verify; returns the plan."""
    payload = {
        "evidence_ids": [evidence_id],
        "intended_state": "Demo worker reports healthy with a fresh heartbeat.",
        "criteria": [
            {
                "description": "Worker status reads healthy.",
                "tool_name": "get_demo_worker_health",
                "tool_args": {},
                "path": "status",
                "op": "eq",
                "expected": "healthy",
            }
        ],
        "guidance": "Restart the worker.",
        "risks": "None.",
        "remediation_kind": "manual",
    }
    plan = client.post(f"/api/investigations/{inv_id}/plans", json=payload).json()["plans"][-1]
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    client.post(
        f"/api/plans/{plan['plan_id']}/interventions/manual",
        json={"description": "Restarted the worker by hand."},
    )
    if monkeypatch is not None:
        monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", flip_to)
    verified = client.post(f"/api/plans/{plan['plan_id']}/verify").json()
    return next(p for p in verified["plans"] if p["plan_id"] == plan["plan_id"])


def test_record_and_match_similar_resolved_incident(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 1: a verified fix is remembered and matched, with reasons."""
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    first = _investigate("The FieldRook demo worker is down.")
    worker_items = [i for i in first["evidence"] if i["category"] == "demo_worker"]
    plan = _resolve_worker(first["investigation_id"], worker_items[0]["id"], monkeypatch)
    assert plan["status"] == "VERIFIED_RESOLVED"

    recorded = client.post(
        f"/api/investigations/{first['investigation_id']}/knowledge", json={}
    )
    assert recorded.status_code == 201, recorded.text
    entry = recorded.json()
    assert entry["outcome"] == "VERIFIED_RESOLVED"
    assert entry["source_investigation_id"] == first["investigation_id"]
    assert entry["criteria"], "measured criteria must be stored"
    assert "demo" in " ".join(entry["symptoms"])

    second = _investigate("The FieldRook demo worker is down again.")
    matches = client.get(
        f"/api/investigations/{second['investigation_id']}/knowledge/matches"
    ).json()["matches"]
    match = next(m for m in matches if m["entry"]["entry_id"] == entry["entry_id"])
    assert match["entry"]["outcome"] == "VERIFIED_RESOLVED"
    assert match["signals"], "every match must explain itself"
    assert any("worker" in s["detail"].lower() for s in match["signals"])
    assert match["strength"] > 0


def _record(inv_id: str, **payload: object) -> dict:
    response = client.post(f"/api/investigations/{inv_id}/knowledge", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_similar_symptoms_different_cause_show_difference(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 2: Excel history vs an Outlook crash — matched, flagged."""
    first = _investigate("Excel keeps crashing when I open large files.")
    recorded = _record(first["investigation_id"])
    monkeypatch.setenv("FIELDROOK_FIXTURE_CRASH_EXTRA", "OUTLOOK.EXE")
    second = _investigate("Outlook keeps crashing when I open large files.")
    matches = client.get(
        f"/api/investigations/{second['investigation_id']}/knowledge/matches"
    ).json()["matches"]
    match = next(m for m in matches if m["entry"]["entry_id"] == recorded["entry_id"])
    assert any(s["signal"] == "category" for s in match["signals"])
    assert any(
        "excel" in diff.lower() and "outlook" in diff.lower()
        for diff in match["differences"]
    ), match["differences"]
    assert "no confidence" not in str(match).lower()


def test_failed_repair_surfaces_without_endorsement(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 3: a NOT_RESOLVED entry matches but is labeled honestly."""
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    first = _investigate("The FieldRook demo worker is down.")
    worker_items = [i for i in first["evidence"] if i["category"] == "demo_worker"]
    plan = _resolve_worker(first["investigation_id"], worker_items[0]["id"])
    assert plan["status"] == "NOT_RESOLVED"
    entry = _record(first["investigation_id"])
    assert entry["outcome"] == "NOT_RESOLVED"

    second = _investigate("The FieldRook demo worker is down again.")
    matches = client.get(
        f"/api/investigations/{second['investigation_id']}/knowledge/matches"
    ).json()["matches"]
    match = next(m for m in matches if m["entry"]["entry_id"] == entry["entry_id"])
    assert match["entry"]["outcome"] == "NOT_RESOLVED"


def test_insufficient_evidence_matches_nothing() -> None:
    """Scenario 4: an unrelated incident finds no historical match."""
    first = _investigate("The FieldRook demo worker is down.")
    _record(first["investigation_id"])
    second = _investigate("My printer prints blank pages every morning.")
    matches = client.get(
        f"/api/investigations/{second['investigation_id']}/knowledge/matches"
    ).json()["matches"]
    assert matches == []


def test_repeated_resolution_merges_without_duplicates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 5: the identical verified fix clusters into one entry."""
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    problem = "The FieldRook demo worker is down again today."
    for _ in range(2):
        body = _investigate(problem)
        worker_items = [i for i in body["evidence"] if i["category"] == "demo_worker"]
        plan = _resolve_worker(body["investigation_id"], worker_items[0]["id"], monkeypatch)
        assert plan["status"] == "VERIFIED_RESOLVED"
        _record(body["investigation_id"])
        monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    entries = client.get("/api/knowledge").json()
    merged = [e for e in entries if e["problem"] == problem]
    assert len(merged) == 1
    assert merged[0]["occurrence_count"] == 2
    assert len(merged[0]["investigations"]) == 2


def test_regression_after_verified_recovery(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 6: fresh failure contradicts a verified entry."""
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    first = _investigate("The FieldRook demo worker is down.")
    worker_items = [i for i in first["evidence"] if i["category"] == "demo_worker"]
    plan = _resolve_worker(first["investigation_id"], worker_items[0]["id"], monkeypatch)
    assert plan["status"] == "VERIFIED_RESOLVED"
    entry = _record(first["investigation_id"])

    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    second = _investigate("The FieldRook demo worker is down again.")
    rechecked = client.post(
        f"/api/investigations/{second['investigation_id']}/knowledge/{entry['entry_id']}/recheck"
    )
    assert rechecked.status_code == 200, rechecked.text
    body = rechecked.json()
    assert len(body["regression_checks"]) == 1
    check = body["regression_checks"][0]
    assert check["outcome"] == "REGRESSION"
    assert check["entry_id"] == entry["entry_id"]
    assert "failed" in check["results"][0]["detail"]
    assert any("regression" in w.lower() for w in body["warnings"])
    # The historical verdict stands untouched.
    assert client.get(f"/api/knowledge/{entry['entry_id']}").json()["outcome"] == "VERIFIED_RESOLVED"
    report = client.get(
        f"/api/investigations/{second['investigation_id']}/export?format=markdown"
    )
    assert "## 16. Knowledge regression checks" in report.text
    assert "REGRESSION" in report.text


def test_recheck_confirms_still_resolved(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    first = _investigate("The FieldRook demo worker is down.")
    worker_items = [i for i in first["evidence"] if i["category"] == "demo_worker"]
    _resolve_worker(first["investigation_id"], worker_items[0]["id"], monkeypatch)
    entry = _record(first["investigation_id"])

    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "healthy")
    second = _investigate("The FieldRook demo worker is down again.")
    body = client.post(
        f"/api/investigations/{second['investigation_id']}/knowledge/{entry['entry_id']}/recheck"
    ).json()
    assert body["regression_checks"][0]["outcome"] == "CONFIRMED"


def test_restart_persistence_and_migration() -> None:
    """Scenario 7: entries and checks survive reload; v4 DBs migrate."""
    import sqlite3

    from app.investigations import persistence

    first = _investigate("The FieldRook demo worker is down.")
    entry = _record(first["investigation_id"])
    listed = client.get("/api/knowledge").json()
    assert entry["entry_id"] in {e["entry_id"] for e in listed}

    db = persistence.db_path()
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        conn.execute("DROP TABLE knowledge")
        conn.execute("DROP TABLE regression_checks")
        conn.execute("PRAGMA user_version = 4")
        conn.commit()
    finally:
        conn.close()
    # Next touch migrates v4 -> v5 without losing investigation rows.
    assert client.get(f"/api/investigations/{first['investigation_id']}").status_code == 200
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"knowledge", "regression_checks"} <= tables
    finally:
        conn.close()


def test_deletion_redaction_and_boundaries() -> None:
    """Scenario 8: secrets masked, entries deletable, origins enforced."""
    first = _investigate("The demo worker is down, contact bob@example.com password=hunter2.")
    entry = _record(first["investigation_id"], confirmed_cause="Technician-verified disk fault.")
    assert "hunter2" not in entry["problem"]
    assert "bob@example.com" not in entry["problem"]
    assert "[secret redacted]" in entry["problem"] or "[email redacted]" in entry["problem"]
    assert entry["root_cause_verified"] is True
    assert entry["root_cause"] == "Technician-verified disk fault."

    exported = client.get(f"/api/knowledge/{entry['entry_id']}/export?format=markdown")
    assert exported.status_code == 200
    assert "hunter2" not in exported.text
    assert "technician-confirmed" in exported.text.lower()

    second = _investigate("The FieldRook demo worker is down.")
    other = _record(second["investigation_id"])
    assert other["entry_id"] != entry["entry_id"]
    single = client.get(f"/api/knowledge/{other['entry_id']}/export?format=markdown").text
    assert other["entry_id"] in single
    assert entry["entry_id"] not in single, "exports must not leak other entries"
    assert "hunter2" not in single
    assert "[email redacted]" not in single

    assert client.delete(f"/api/knowledge/{entry['entry_id']}").status_code == 200
    assert client.get(f"/api/knowledge/{entry['entry_id']}").status_code == 404
    assert client.delete(f"/api/knowledge/{entry['entry_id']}").status_code == 404

    evil = {"Origin": "https://evil.example"}
    assert (
        client.post(
            f"/api/investigations/{second['investigation_id']}/knowledge",
            json={},
            headers=evil,
        ).status_code
        == 403
    )
    assert client.delete(f"/api/knowledge/{other['entry_id']}", headers=evil).status_code == 403


def test_recheck_rejects_unverified_entries() -> None:
    first = _investigate("The FieldRook demo worker is down.")
    entry = _record(first["investigation_id"])
    assert entry["outcome"] == "UNRESOLVED"
    second = _investigate("The FieldRook demo worker is down again.")
    refused = client.post(
        f"/api/investigations/{second['investigation_id']}/knowledge/{entry['entry_id']}/recheck"
    )
    assert refused.status_code == 422
