"""Corrective actions: approval enforcement, lifecycle, failure modes."""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.actions import demo_worker
from app.actions.approval import approve, create_proposal, reject
from app.actions.executor import execute_approved
from app.actions import registry as action_registry
from app.actions.registry import (
    ActionDisabledError,
    ApprovalError,
    ArgsValidationError,
    PreconditionError,
    TargetNotAllowedError,
    UnknownActionError,
)
from app.investigations import persistence
from app.investigations.store import InvestigationState, store
from app.main import app

client = TestClient(app)


def _state() -> InvestigationState:
    return store.create(problem="Demo worker is down.", service_name=None, has_image=False)


class _Worker:
    """Real demo worker subprocess in an isolated state dir."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        script = demo_worker.worker_script()
        self.proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if demo_worker.read_health().get("status") == "healthy":
                return
            time.sleep(0.5)
        raise RuntimeError("worker did not become healthy")

    def fail(self) -> None:
        demo_worker.write_control("failing")
        deadline = time.time() + 20
        while time.time() < deadline:
            if demo_worker.read_health().get("status") == "failed":
                return
            time.sleep(0.5)
        raise RuntimeError("worker did not report failed")

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            demo_worker.terminate_verified_worker(self.proc.pid)
            self.proc.wait(timeout=15)


def test_recovery_lifecycle_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker = _Worker(monkeypatch, tmp_path)
    worker.start()
    try:
        worker.fail()
        state = _state()
        proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "E2E test.", [])
        assert proposal.status == "AWAITING_APPROVAL"
        token = approve(state, proposal.proposal_id)
        execution = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
        assert execution.outcome == "VERIFIED_RESOLVED"
        assert proposal.status == "VERIFIED_RESOLVED"
        assert execution.before_state.get("status") == "failed"
        assert execution.after_state.get("status") == "healthy"
        assert demo_worker.read_health().get("status") == "healthy"
    finally:
        worker.stop()


def test_reject_leaves_system_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker = _Worker(monkeypatch, tmp_path)
    worker.start()
    try:
        worker.fail()
        control = tmp_path / "control.json"
        before = control.read_text(encoding="utf-8")
        state = _state()
        proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Reject test.", [])
        reject(state, proposal.proposal_id, "Not now.")
        assert proposal.status == "REJECTED"
        assert control.read_text(encoding="utf-8") == before
        assert demo_worker.read_health().get("status") == "failed"
        assert state.executions == []
        with pytest.raises(ApprovalError):
            asyncio.run(execute_approved(state, proposal.proposal_id, "bogus", {}))
    finally:
        worker.stop()


def test_execute_without_approval_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "No approval.", [])
    with pytest.raises(ApprovalError):
        asyncio.run(execute_approved(state, proposal.proposal_id, "bogus", {}))
    assert proposal.status == "AWAITING_APPROVAL"
    assert state.executions == []


def test_expired_approval_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Expiry.", [])
    token = approve(state, proposal.proposal_id)
    proposal.approval_expires_at = 1.0
    with pytest.raises(ApprovalError, match="expired"):
        asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))


def test_expired_approval_allows_reapproval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Reapprove.", [])
    token = approve(state, proposal.proposal_id)
    assert proposal.status == "APPROVED"
    proposal.approval_expires_at = 1.0
    with pytest.raises(ApprovalError, match="expired"):
        asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert proposal.status == "AWAITING_APPROVAL"
    assert proposal.decision is None
    assert state.executions == []
    fresh = approve(state, proposal.proposal_id)
    assert proposal.status == "APPROVED"
    assert fresh != token


def test_replayed_approval_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker = _Worker(monkeypatch, tmp_path)
    worker.start()
    try:
        worker.fail()
        state = _state()
        proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Replay.", [])
        token = approve(state, proposal.proposal_id)
        first = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
        assert first.outcome == "VERIFIED_RESOLVED"
        with pytest.raises(ApprovalError):
            asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
        assert len(state.executions) == 1
    finally:
        worker.stop()


def test_modified_args_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Tamper.", [])
    token = approve(state, proposal.proposal_id)
    with pytest.raises(ApprovalError, match="differ"):
        asyncio.run(execute_approved(state, proposal.proposal_id, token, {"x": 1}))


def test_disallowed_target_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    with pytest.raises(TargetNotAllowedError):
        create_proposal(_state(), "recover_demo_worker", "prod-db", {}, "Bad target.", [])


def test_unknown_action_rejected() -> None:
    with pytest.raises(UnknownActionError):
        create_proposal(_state(), "format_drive", "demo-worker", {}, "Bad action.", [])


def test_malformed_args_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    with pytest.raises(ArgsValidationError):
        create_proposal(_state(), "recover_demo_worker", "demo-worker", {"x": 1}, "Bad args.", [])


def test_precondition_blocks_healthy_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker = _Worker(monkeypatch, tmp_path)
    worker.start()
    try:
        with pytest.raises(PreconditionError):
            create_proposal(_state(), "recover_demo_worker", "demo-worker", {}, "Nothing wrong.", [])
    finally:
        worker.stop()


def test_actions_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELDROOK_ACTIONS_ENABLED", "0")
    with pytest.raises(ActionDisabledError):
        create_proposal(_state(), "recover_demo_worker", "demo-worker", {}, "Disabled.", [])


def test_concurrent_execution_single_winner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker = _Worker(monkeypatch, tmp_path)
    worker.start()
    try:
        worker.fail()
        state = _state()
        proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Race.", [])
        token = approve(state, proposal.proposal_id)
        errors: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait(timeout=10)
            try:
                asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
            except ApprovalError as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        assert len(state.executions) == 1
        assert len(errors) == 1
    finally:
        worker.stop()


def _stub_spec(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    from dataclasses import replace

    real = action_registry.REGISTRY["recover_demo_worker"]
    monkeypatch.setitem(action_registry.REGISTRY, "recover_demo_worker", replace(real, **overrides))


def test_execution_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))

    def slow(args: dict) -> dict:
        time.sleep(30)
        return {}

    _stub_spec(monkeypatch, timeout_s=0.5, execute=slow)
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Timeout.", [])
    token = approve(state, proposal.proposal_id)
    execution = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert execution.outcome == "EXECUTION_FAILED"
    assert execution.error is not None and "timeout" in execution.error.lower()


def test_action_failure_recorded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))

    def boom(args: dict) -> dict:
        raise RuntimeError("boom")

    _stub_spec(monkeypatch, execute=boom)
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Boom.", [])
    token = approve(state, proposal.proposal_id)
    execution = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert execution.outcome == "EXECUTION_FAILED"
    assert execution.error is not None and "boom" in execution.error


def test_verification_error_recorded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))

    def bad_verify() -> tuple[bool, dict]:
        raise RuntimeError("verifier exploded")

    _stub_spec(monkeypatch, execute=lambda args: {"after": {}}, verify=bad_verify)
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Verify boom.", [])
    token = approve(state, proposal.proposal_id)
    execution = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert execution.outcome == "VERIFICATION_FAILED"


def test_unresolved_when_still_failing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    _stub_spec(
        monkeypatch,
        execute=lambda args: {"after": {}},
        verify=lambda: (False, {"status": "failed"}),
    )
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Unresolved.", [])
    token = approve(state, proposal.proposal_id)
    execution = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert execution.outcome == "VERIFIED_UNRESOLVED"


def test_investigation_change_invalidates_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Stale.", [])
    token = approve(state, proposal.proposal_id)
    state.add_evidence(category="note", source="test", data={})
    with pytest.raises(ApprovalError, match="changed"):
        asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert proposal.status == "AWAITING_APPROVAL"
    assert proposal.decision is None


def test_restart_recovery_marks_executing_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Stuck.", [])
    proposal.status = "EXECUTING"
    from app.investigations.store import store as live_store

    live_store.save(state)
    assert persistence.fail_stuck_executions() >= 1
    reloaded = live_store.get(state.id)
    assert reloaded is not None
    assert reloaded.proposals[0].status == "EXECUTION_FAILED"
    assert any(r.kind == "error" for r in reloaded.activity)


def test_approve_reissues_unused_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    state = _state()
    proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Reissue.", [])
    first = approve(state, proposal.proposal_id)
    second = approve(state, proposal.proposal_id)
    assert second != first
    assert proposal.status == "APPROVED"
    with pytest.raises(ApprovalError, match="mismatch"):
        asyncio.run(execute_approved(state, proposal.proposal_id, first, {}))
    assert proposal.status == "APPROVED"  # stale token changes nothing


def test_approve_refuses_after_use(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker = _Worker(monkeypatch, tmp_path)
    worker.start()
    try:
        worker.fail()
        state = _state()
        proposal = create_proposal(state, "recover_demo_worker", "demo-worker", {}, "Used.", [])
        token = approve(state, proposal.proposal_id)
        asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
        with pytest.raises(ApprovalError):
            approve(state, proposal.proposal_id)
    finally:
        worker.stop()


def test_reject_accepts_bodiless_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    started = client.post("/api/investigations", data={"problem": "Demo worker is down."})
    inv_id = started.json()["investigation_id"]
    created = client.post(
        f"/api/investigations/{inv_id}/proposals",
        json={"action_id": "recover_demo_worker", "target": "demo-worker", "reason": "UI shape."},
    )
    proposal_id = created.json()["proposals"][-1]["proposal_id"]
    refused = client.post(
        f"/api/proposals/{proposal_id}/reject", headers={"Origin": "https://evil.example"}
    )
    assert refused.status_code == 403
    # M025: headerless POSTs stay allowed ON PURPOSE — non-browser clients
    # (curl, TestClient, desktop launcher) send no Origin/Referer and no
    # Sec-Fetch-Site. Cross-site *browser* requests are still blocked because
    # browsers attach Sec-Fetch-Site: cross-site (see test_desktop_security).
    bodiless = client.post(f"/api/proposals/{proposal_id}/reject")
    assert bodiless.status_code == 200
    assert bodiless.json()["proposals"][-1]["status"] == "REJECTED"


def test_no_shell_execution_surface() -> None:
    actions_dir = Path(demo_worker.__file__).resolve().parent
    for path in sorted(actions_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text, path.name
        assert "os.system" not in text, path.name
    assert set(action_registry.REGISTRY) == {"recover_demo_worker"}


def test_cross_origin_mutations_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    started = client.post("/api/investigations", data={"problem": "Demo worker is down."})
    assert started.status_code == 200
    inv_id = started.json()["investigation_id"]
    evil = {"Origin": "https://evil.example"}
    refused = client.post(
        f"/api/investigations/{inv_id}/proposals",
        json={"action_id": "recover_demo_worker", "target": "demo-worker", "reason": "CSRF test."},
        headers=evil,
    )
    assert refused.status_code == 403
    # M025: no-Origin headerless posts are the non-browser allowance (curl /
    # TestClient / launcher); real cross-site browsers send Sec-Fetch-Site
    # and are rejected (see test_desktop_security.py).
    created = client.post(
        f"/api/investigations/{inv_id}/proposals",
        json={"action_id": "recover_demo_worker", "target": "demo-worker", "reason": "CSRF test."},
    )
    assert created.status_code == 200
    proposal_id = created.json()["proposals"][-1]["proposal_id"]
    refused_approve = client.post(f"/api/proposals/{proposal_id}/approve", headers=evil)
    assert refused_approve.status_code == 403
    approved = client.post(f"/api/proposals/{proposal_id}/approve")
    assert approved.status_code == 200
    token = approved.json()["approval_token"]
    refused_execute = client.post(
        f"/api/proposals/{proposal_id}/execute",
        json={"approval_token": token, "args": {}},
        headers=evil,
    )
    assert refused_execute.status_code == 403


def test_terminate_refuses_foreign_process() -> None:
    with pytest.raises(demo_worker.WorkerError, match="Refusing"):
        demo_worker.terminate_verified_worker(4)  # System process: never ours
    assert demo_worker.is_own_worker_process(4) is False
    assert demo_worker.is_own_worker_process(-1) is False
    assert demo_worker.is_own_worker_process("1234") is False  # type: ignore[arg-type]
