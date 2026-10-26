"""Persistence: restart survival, stable ids, migration, no secrets stored."""

import json
import sqlite3

from app.investigations import persistence
from app.investigations.store import store
from app.schemas import AnalysisResult


def _rich_state() -> object:
    state = store.create(problem="Persistence probe.", service_name=None, has_image=True)
    state.messages.append({"role": "user", "content": "hi"})
    state.messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "see attached"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAABBBBCCCC"}},
            ],
        }
    )
    item = state.add_evidence(category="os_info", source="fixture", data={"a": 1})
    state.add_activity("note", "hello", "world", evidence_ids=[item.id])
    state.assessment = AnalysisResult(
        summary="s",
        facts=[],
        causes=[],
        uncertainties=[],
        missing_evidence=[],
        next_actions=[],
        explanation="e",
        mode="simulated",
        model="m",
    )
    return state


def test_restart_survival_reloads_state() -> None:
    state = _rich_state()
    store.save(state)
    reloaded = store.get(state.id)
    assert reloaded is not None
    assert reloaded.problem == state.problem
    assert [item.id for item in reloaded.evidence] == [item.id for item in state.evidence]
    assert [record.seq for record in reloaded.activity] == [record.seq for record in state.activity]
    assert reloaded.assessment is not None
    assert reloaded.assessment.summary == "s"
    assert reloaded.ev_counter == state.ev_counter
    assert reloaded.seq_counter == state.seq_counter


def test_image_bytes_never_persisted() -> None:
    state = _rich_state()
    store.save(state)
    conn = sqlite3.connect(str(persistence.db_path()))
    try:
        blob = "\n".join(
            row[0]
            for row in conn.execute("SELECT content_json FROM messages WHERE inv_id = ?", (state.id,))
        )
    finally:
        conn.close()
    assert "AAAABBBBCCCC" not in blob
    assert "redacted from stored history" in blob


def test_approval_tokens_stored_as_hashes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import tempfile

    from app.actions.approval import approve, create_proposal

    monkeypatch.setenv("FIELDROOK_DEMO_STATE", tempfile.mkdtemp(prefix="fieldrook-demo-"))
    state = store.create(problem="Token probe.", service_name=None, has_image=False)
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Probe.", [])
    token = approve(state, proposal.proposal_id)
    store.save(state)
    raw = persistence.db_path().read_bytes()
    assert token.encode("utf-8") not in raw
    conn = sqlite3.connect(str(persistence.db_path()))
    try:
        stored = conn.execute(
            "SELECT approval_token_hash FROM proposals WHERE proposal_id = ?",
            (proposal.proposal_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert stored and stored != token


def test_list_recent_orders_and_counts() -> None:
    first = store.create(problem="First probe.", service_name=None, has_image=False)
    second = store.create(problem="Second probe.", service_name=None, has_image=False)
    summaries = store.list_recent(limit=50)
    ids = [s.investigation_id for s in summaries]
    assert first.id in ids and second.id in ids
    assert ids.index(second.id) < ids.index(first.id)
    match = next(s for s in summaries if s.investigation_id == second.id)
    assert match.proposal_count == 0
    assert match.latest_outcome is None
    assert match.evidence_count == 0


def test_summary_reports_evidence_count() -> None:
    state = store.create(problem="Count probe.", service_name=None, has_image=False)
    state.add_evidence(category="os_info", source="fixture", data={"a": 1})
    state.add_evidence(category="os_info", source="fixture", data={"b": 2})
    store.save(state)
    match = next(s for s in store.list_recent(limit=200) if s.investigation_id == state.id)
    assert match.evidence_count == 2


def test_migration_initializes_fresh_db(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    fresh = tmp_path / "fresh.db"
    monkeypatch.setenv("FIELDROOK_DB_PATH", str(fresh))
    conn = sqlite3.connect(str(fresh))
    try:
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()
    state = store.create(problem="Migration probe.", service_name=None, has_image=False)
    assert store.get(state.id) is not None
    conn = sqlite3.connect(str(fresh))
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert version == persistence.DB_VERSION
    assert {"investigations", "evidence", "proposals", "executions"} <= tables
