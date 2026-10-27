"""SQLite persistence for investigations (stdlib sqlite3, versioned schema).

Stores problems, evidence, assessments, tool activity, proposals, approvals,
and executions so incident history survives backend restarts. Screenshots are
never persisted: image bytes are stripped from stored message history.
Approval tokens are stored as hashes only. No credentials are ever written.
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_VERSION = 2

_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS notes (
    note_id TEXT PRIMARY KEY,
    inv_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    problem TEXT NOT NULL,
    service_name TEXT,
    has_image INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'complete',
    mode TEXT NOT NULL DEFAULT 'simulated',
    model TEXT NOT NULL DEFAULT '',
    tool_calls_made INTEGER NOT NULL DEFAULT 0,
    ev_counter INTEGER NOT NULL DEFAULT 0,
    seq_counter INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    inv_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    content_json TEXT NOT NULL,
    PRIMARY KEY (inv_id, seq)
);
CREATE TABLE IF NOT EXISTS evidence (
    inv_id TEXT NOT NULL,
    ev_id TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    data_json TEXT NOT NULL,
    error TEXT,
    PRIMARY KEY (inv_id, ev_id)
);
CREATE TABLE IF NOT EXISTS activity (
    inv_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    tool_name TEXT,
    duration_ms INTEGER,
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (inv_id, seq)
);
CREATE TABLE IF NOT EXISTS assessments (
    inv_id TEXT PRIMARY KEY,
    assessment_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    inv_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    target TEXT NOT NULL,
    args_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL DEFAULT '',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    risk TEXT NOT NULL DEFAULT 'low',
    action_description TEXT NOT NULL DEFAULT '',
    expected_result TEXT NOT NULL DEFAULT '',
    verification_method TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decision TEXT,
    approval_token_hash TEXT,
    approval_expires_at REAL,
    approval_used INTEGER NOT NULL DEFAULT 0,
    approval_args_hash TEXT,
    approval_digest TEXT
);
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL DEFAULT '',
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
"""


def db_path() -> Path:
    override = os.environ.get("FIELDROOK_DB_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "fieldrook.db"


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0] or 0
    if version < 1:
        conn.executescript(_SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
    if version < 2:
        conn.executescript(_SCHEMA_V2)
        conn.execute("PRAGMA user_version = 2")
    conn.commit()


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def strip_images_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deep-copy chat history with image data URLs removed (metadata kept)."""
    cleaned = copy.deepcopy(messages)
    for message in cleaned:
        content = message.get("content")
        if isinstance(content, list):
            texts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            had_image = any(
                isinstance(part, dict) and part.get("type") == "image_url" for part in content
            )
            texts.append(
                "[screenshot redacted from stored history]"
                if had_image
                else "[content blocks redacted from stored history]"
            )
            message["content"] = "\n".join(text for text in texts if text)
    return cleaned


def save_state(state: Any) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO investigations (id, problem, service_name, has_image, status, mode, model,"
            " tool_calls_made, ev_counter, seq_counter, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET problem=excluded.problem, service_name=excluded.service_name,"
            " has_image=excluded.has_image, status=excluded.status, mode=excluded.mode, model=excluded.model,"
            " tool_calls_made=excluded.tool_calls_made, ev_counter=excluded.ev_counter,"
            " seq_counter=excluded.seq_counter, updated_at=excluded.updated_at",
            (
                state.id,
                state.problem,
                state.service_name,
                1 if state.has_image else 0,
                state.status,
                state.mode,
                state.model,
                state.tool_calls_made,
                state.ev_counter,
                state.seq_counter,
                _iso(state.created_at),
                _iso(state.updated_at),
            ),
        )
        conn.execute("DELETE FROM messages WHERE inv_id = ?", (state.id,))
        for seq, message in enumerate(strip_images_from_messages(state.messages)):
            conn.execute(
                "INSERT INTO messages (inv_id, seq, role, content_json) VALUES (?, ?, ?, ?)",
                (state.id, seq, str(message.get("role", "")), json.dumps(message, default=str)),
            )
        conn.execute("DELETE FROM evidence WHERE inv_id = ?", (state.id,))
        for item in state.evidence:
            conn.execute(
                "INSERT INTO evidence (inv_id, ev_id, category, source, collected_at, data_json, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    state.id,
                    item.id,
                    item.category,
                    item.source,
                    _iso(item.collected_at),
                    json.dumps(item.data, default=str),
                    item.error,
                ),
            )
        conn.execute("DELETE FROM activity WHERE inv_id = ?", (state.id,))
        for record in state.activity:
            conn.execute(
                "INSERT INTO activity (inv_id, seq, kind, title, detail, tool_name, duration_ms, evidence_ids_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    state.id,
                    record.seq,
                    record.kind,
                    record.title,
                    record.detail,
                    record.tool_name,
                    record.duration_ms,
                    json.dumps(record.evidence_ids),
                ),
            )
        if state.assessment is not None:
            conn.execute(
                "INSERT INTO assessments (inv_id, assessment_json) VALUES (?, ?)"
                " ON CONFLICT(inv_id) DO UPDATE SET assessment_json=excluded.assessment_json",
                (state.id, state.assessment.model_dump_json()),
            )
        conn.execute("DELETE FROM proposals WHERE inv_id = ?", (state.id,))
        for proposal in state.proposals:
            conn.execute(
                "INSERT INTO proposals (proposal_id, inv_id, action_id, target, args_json, reason,"
                " evidence_ids_json, risk, action_description, expected_result, verification_method,"
                " status, created_at, decided_at, decision, approval_token_hash, approval_expires_at,"
                " approval_used, approval_args_hash, approval_digest)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal.proposal_id,
                    state.id,
                    proposal.action_id,
                    proposal.target,
                    json.dumps(proposal.args, default=str),
                    proposal.reason,
                    json.dumps(proposal.evidence_ids),
                    proposal.risk,
                    proposal.action_description,
                    proposal.expected_result,
                    proposal.verification_method,
                    proposal.status,
                    _iso(proposal.created_at),
                    _iso(proposal.decided_at) if proposal.decided_at else None,
                    proposal.decision,
                    proposal.approval_token_hash,
                    proposal.approval_expires_at,
                    1 if proposal.approval_used else 0,
                    proposal.approval_args_hash,
                    proposal.approval_digest,
                ),
            )
        conn.execute("DELETE FROM notes WHERE inv_id = ?", (state.id,))
        for note in getattr(state, "notes", []) or []:
            conn.execute(
                "INSERT INTO notes (note_id, inv_id, text, created_at) VALUES (?, ?, ?, ?)",
                (note.note_id, state.id, note.text, _iso(note.created_at)),
            )
        for execution in state.executions:
            conn.execute(
                "INSERT INTO executions (execution_id, proposal_id, before_json, after_json, outcome,"
                " error, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(execution_id) DO UPDATE SET before_json=excluded.before_json,"
                " after_json=excluded.after_json, outcome=excluded.outcome, error=excluded.error,"
                " finished_at=excluded.finished_at",
                (
                    execution.execution_id,
                    execution.proposal_id,
                    json.dumps(execution.before_state, default=str),
                    json.dumps(execution.after_state, default=str),
                    execution.outcome,
                    execution.error,
                    _iso(execution.started_at),
                    _iso(execution.finished_at) if execution.finished_at else None,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _parse_dt(text: str | None) -> datetime:
    if not text:
        return datetime.now().astimezone()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now().astimezone()
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def load_state(investigation_id: str) -> Any | None:
    from ..schemas import (
        ActionExecution,
        ActionProposal,
        ActivityRecord,
        AnalysisResult,
        EvidenceItem,
        TechnicianNote,
    )
    from .store import InvestigationState

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM investigations WHERE id = ?", (investigation_id,)
        ).fetchone()
        if row is None:
            return None
        messages = [
            json.loads(m["content_json"])
            for m in conn.execute(
                "SELECT content_json FROM messages WHERE inv_id = ? ORDER BY seq", (investigation_id,)
            ).fetchall()
        ]
        evidence = [
            EvidenceItem(
                id=e["ev_id"],
                category=e["category"],
                source=e["source"],
                collected_at=_parse_dt(e["collected_at"]),
                data=json.loads(e["data_json"]),
                error=e["error"],
            )
            for e in conn.execute(
                "SELECT * FROM evidence WHERE inv_id = ? ORDER BY rowid", (investigation_id,)
            ).fetchall()
        ]
        activity = [
            ActivityRecord(
                seq=a["seq"],
                kind=a["kind"],
                title=a["title"],
                detail=a["detail"] or "",
                tool_name=a["tool_name"],
                duration_ms=a["duration_ms"],
                evidence_ids=json.loads(a["evidence_ids_json"] or "[]"),
            )
            for a in conn.execute(
                "SELECT * FROM activity WHERE inv_id = ? ORDER BY seq", (investigation_id,)
            ).fetchall()
        ]
        assessment_row = conn.execute(
            "SELECT assessment_json FROM assessments WHERE inv_id = ?", (investigation_id,)
        ).fetchone()
        proposals = [
            ActionProposal(
                proposal_id=p["proposal_id"],
                investigation_id=investigation_id,
                action_id=p["action_id"],
                target=p["target"],
                args=json.loads(p["args_json"] or "{}"),
                reason=p["reason"] or "",
                evidence_ids=json.loads(p["evidence_ids_json"] or "[]"),
                risk=p["risk"] or "low",
                action_description=p["action_description"] or "",
                expected_result=p["expected_result"] or "",
                verification_method=p["verification_method"] or "",
                status=p["status"] or "PROPOSED",
                created_at=_parse_dt(p["created_at"]),
                decided_at=_parse_dt(p["decided_at"]) if p["decided_at"] else None,
                decision=p["decision"],
                approval_token_hash=p["approval_token_hash"],
                approval_expires_at=p["approval_expires_at"],
                approval_used=bool(p["approval_used"]),
                approval_args_hash=p["approval_args_hash"],
                approval_digest=p["approval_digest"],
            )
            for p in conn.execute(
                "SELECT * FROM proposals WHERE inv_id = ? ORDER BY rowid", (investigation_id,)
            ).fetchall()
        ]
        executions = [
            ActionExecution(
                execution_id=x["execution_id"],
                proposal_id=x["proposal_id"],
                before_state=json.loads(x["before_json"] or "{}"),
                after_state=json.loads(x["after_json"] or "{}"),
                outcome=x["outcome"] or "",
                error=x["error"],
                started_at=_parse_dt(x["started_at"]),
                finished_at=_parse_dt(x["finished_at"]) if x["finished_at"] else None,
            )
            for x in conn.execute(
                "SELECT executions.* FROM executions JOIN proposals ON executions.proposal_id ="
                " proposals.proposal_id WHERE proposals.inv_id = ? ORDER BY executions.rowid",
                (investigation_id,),
            ).fetchall()
        ]
        notes = [
            TechnicianNote(
                note_id=n["note_id"],
                text=n["text"] or "",
                created_at=_parse_dt(n["created_at"]),
            )
            for n in conn.execute(
                "SELECT * FROM notes WHERE inv_id = ? ORDER BY rowid", (investigation_id,)
            ).fetchall()
        ]
        return InvestigationState(
            id=row["id"],
            problem=row["problem"],
            service_name=row["service_name"],
            has_image=bool(row["has_image"]),
            messages=messages,
            evidence=evidence,
            activity=activity,
            notes=notes,
            assessment=AnalysisResult.model_validate_json(assessment_row["assessment_json"])
            if assessment_row
            else None,
            warnings=[],
            status=row["status"] or "complete",
            tool_calls_made=row["tool_calls_made"] or 0,
            ev_counter=row["ev_counter"] or 0,
            seq_counter=row["seq_counter"] or 0,
            mode=row["mode"] or "simulated",
            model=row["model"] or "",
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            proposals=proposals,
            executions=executions,
        )
    finally:
        conn.close()


def list_states(limit: int = 50) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, problem, status, mode, model, created_at, updated_at FROM investigations"
            " ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
        summaries = []
        for row in rows:
            outcome = conn.execute(
                "SELECT outcome FROM executions JOIN proposals ON executions.proposal_id ="
                " proposals.proposal_id WHERE proposals.inv_id = ? ORDER BY executions.rowid DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            proposal_count = conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE inv_id = ?", (row["id"],)
            ).fetchone()[0]
            evidence_count = conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE inv_id = ?", (row["id"],)
            ).fetchone()[0]
            summaries.append(
                {
                    "investigation_id": row["id"],
                    "problem": row["problem"],
                    "status": row["status"],
                    "analysis_mode": row["mode"],
                    "model": row["model"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "evidence_count": evidence_count,
                    "proposal_count": proposal_count,
                    "latest_outcome": outcome["outcome"] if outcome else None,
                }
            )
        return summaries
    finally:
        conn.close()


def find_proposal(proposal_id: str) -> str | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT inv_id FROM proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
        return row["inv_id"] if row else None
    finally:
        conn.close()


def fail_stuck_executions() -> int:
    """Fail-closed recovery: proposals stuck mid-execution never assume success."""
    conn = _connect()
    try:
        stuck = conn.execute(
            "SELECT proposal_id, inv_id FROM proposals WHERE status = 'EXECUTING'"
        ).fetchall()
        for row in stuck:
            conn.execute(
                "UPDATE proposals SET status = 'EXECUTION_FAILED' WHERE proposal_id = ?",
                (row["proposal_id"],),
            )
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM activity WHERE inv_id = ?",
                (row["inv_id"],),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO activity (inv_id, seq, kind, title, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    row["inv_id"],
                    seq,
                    "error",
                    "Execution interrupted",
                    "Backend restarted during execution; marked failed without assuming success.",
                ),
            )
        conn.commit()
        return len(stuck)
    finally:
        conn.close()
