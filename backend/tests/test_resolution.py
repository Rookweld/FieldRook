"""M008 guided resolution: plans, baselines, interventions, verification."""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.actions import demo_worker
from app.actions.approval import approve, create_proposal
from app.actions.executor import execute_approved
from app.config import load_settings
from app.investigations.store import store
from app.main import app
from app.resolutions import service as plans

client = TestClient(app)


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


def test_registered_repair_verifies_resolved_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 1: real recovery, measured healthy through the plan."""
    worker = _Worker(monkeypatch, tmp_path)
    monkeypatch.setenv("FIELDROOK_FIXTURES", "never")  # live worker reads
    worker.start()
    try:
        worker.fail()
        state = store.create(
            problem="Demo worker is down.", service_name=None, has_image=False
        )
        state.mode = "live"  # plan diagnostics read the live worker, like prod
        seed = state.add_evidence(
            category="demo_worker",
            source="tool:get_demo_worker_health:live",
            data={"summary": "seed", "warnings": [], "status": "failed"},
            tool_name="get_demo_worker_health",
            tool_args={},
        )
        plan = plans.create_plan(state, _worker_plan(seed.id))
        settings = load_settings()
        asyncio.run(plans.capture_baseline(state, plan, settings))
        assert plan.baseline_values[plan.criteria[0].criterion_id] == "failed"
        proposal = create_proposal(
            state, "recover_demo_worker", "demo-worker", {}, "Scenario 1.", []
        )
        token = approve(state, proposal.proposal_id)
        execution = asyncio.run(
            execute_approved(state, proposal.proposal_id, token, {})
        )
        assert execution.outcome == "VERIFIED_RESOLVED"
        plans.link_execution(state, plan, execution.execution_id)
        verification = asyncio.run(plans.verify_plan(state, plan, settings))
        assert verification.outcome == "VERIFIED_RESOLVED"
        assert plan.status == "VERIFIED_RESOLVED"
        assert all(r.outcome == "pass" for r in verification.results)
    finally:
        worker.stop()


def test_executed_action_can_still_not_resolve(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 2: execution succeeds but the criteria stay contradicted."""
    from app.actions import registry as action_registry

    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path))
    real = action_registry.REGISTRY["recover_demo_worker"]
    from dataclasses import replace

    monkeypatch.setitem(
        action_registry.REGISTRY,
        "recover_demo_worker",
        replace(
            real,
            execute=lambda args: {"after": {}},
            verify=lambda: (True, {"status": "healthy"}),
        ),
    )
    state = store.create(
        problem="Windows Update service is down.", service_name="wuauserv", has_image=False
    )
    seed = state.add_evidence(
        category="service_details",
        source="tool:get_service_details:fixture",
        data={"summary": "seed", "warnings": []},
        tool_name="get_service_details",
        tool_args={"name": "wuauserv"},
    )
    payload = _manual_worker_plan(seed.id)
    payload["intended_state"] = "Windows Update service reports Running."
    payload["criteria"] = [
        {
            "description": "Service status reads Running.",
            "tool_name": "get_service_details",
            "tool_args": {"name": "wuauserv"},
            "path": "status.status",
            "op": "eq",
            "expected": "Running",
        }
    ]
    plan = plans.create_plan(state, payload)
    settings = load_settings()
    asyncio.run(plans.capture_baseline(state, plan, settings))
    proposal = create_proposal(
        state, "recover_demo_worker", "demo-worker", {}, "Scenario 2.", []
    )
    token = approve(state, proposal.proposal_id)
    execution = asyncio.run(execute_approved(state, proposal.proposal_id, token, {}))
    assert execution.outcome == "VERIFIED_RESOLVED"  # the action did its own job
    plans.link_execution(state, plan, execution.execution_id)
    verification = asyncio.run(plans.verify_plan(state, plan, settings))
    # ...but the plan's criteria measure a different problem: still Stopped.
    assert verification.outcome == "NOT_RESOLVED"
    assert verification.results[0].outcome == "fail"


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200
    return response.json()


def _worker_plan(evidence_id: str) -> dict:
    return {
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
        "guidance": "Recover the demo worker, then confirm.",
        "risks": "None: application-owned demo resource.",
        "remediation_kind": "action",
        "action_id": "recover_demo_worker",
        "target": "demo-worker",
    }


def test_create_plan_from_template_and_baseline() -> None:
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    assert worker_items

    template = client.get("/api/plans/template?action_id=recover_demo_worker").json()
    assert template["action_id"] == "recover_demo_worker"
    assert template["criteria"], "template must suggest measurable criteria"

    created = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_worker_plan(worker_items[0]["id"]),
    )
    assert created.status_code == 200, created.text
    plan = created.json()["plans"][-1]
    assert plan["plan_id"].startswith("plan-")
    assert plan["status"] == "DRAFT"
    assert plan["criteria"][0]["criterion_id"].startswith("crit-")

    baselined = client.post(f"/api/plans/{plan['plan_id']}/baseline")
    assert baselined.status_code == 200, baselined.text
    plan = baselined.json()["plans"][-1]
    assert plan["status"] == "BASELINED"
    assert plan["baseline_captured_at"]
    assert len(plan["baseline_evidence_ids"]) == 1
    assert plan["baseline_values"][plan["criteria"][0]["criterion_id"]] == "healthy"


def _manual_worker_plan(evidence_id: str) -> dict:
    plan = _worker_plan(evidence_id)
    plan["remediation_kind"] = "manual"
    del plan["action_id"]
    del plan["target"]
    return plan


def _plan_of(body: dict, plan_id: str) -> dict:
    return next(p for p in body["plans"] if p["plan_id"] == plan_id)


def test_manual_repair_measured_recovery(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 3: technician fix, independently measured healthy."""
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    created = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_manual_worker_plan(worker_items[0]["id"]),
    )
    assert created.status_code == 200
    plan = created.json()["plans"][-1]
    baselined = client.post(f"/api/plans/{plan['plan_id']}/baseline").json()
    plan = _plan_of(baselined, plan["plan_id"])
    assert plan["baseline_values"][plan["criteria"][0]["criterion_id"]] == "failed"

    manual = client.post(
        f"/api/plans/{plan['plan_id']}/interventions/manual",
        json={"description": "Restarted the demo worker process by hand."},
    )
    assert manual.status_code == 200
    # The technician's claim alone proves nothing: no verification yet.
    assert _plan_of(manual.json(), plan["plan_id"])["status"] == "INTERVENED"

    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "healthy")
    verified = client.post(f"/api/plans/{plan['plan_id']}/verify").json()
    plan = _plan_of(verified, plan["plan_id"])
    assert plan["status"] == "VERIFIED_RESOLVED"
    check = plan["verifications"][-1]
    assert check["outcome"] == "VERIFIED_RESOLVED"
    assert check["results"][0]["outcome"] == "pass"
    assert check["results"][0]["before_evidence_id"] in plan["baseline_evidence_ids"]
    assert check["results"][0]["after_evidence_id"] in check["after_evidence_ids"]
    assert any("manual" in u.lower() for u in check["uncertainties"])
    # M007 lineage: the AFTER reading supersedes the baseline item.
    assert any(
        r["old_evidence_id"] in plan["baseline_evidence_ids"]
        for r in verified["refreshes"]
    )


def test_contradicted_recovery_is_not_resolved(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 4: one criterion passes, another contradicts it."""
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "failing")
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    payload = _manual_worker_plan(worker_items[0]["id"])
    payload["criteria"].append(
        {
            "description": "Windows Update service is running.",
            "tool_name": "get_service_details",
            "tool_args": {"name": "wuauserv"},
            "path": "status.status",
            "op": "eq",
            "expected": "Running",
        }
    )
    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans", json=payload
    ).json()["plans"][-1]
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    client.post(
        f"/api/plans/{plan['plan_id']}/interventions/manual",
        json={"description": "Restarted the demo worker by hand."},
    )
    monkeypatch.setenv("FIELDROOK_FIXTURE_WORKER", "healthy")
    verified = client.post(f"/api/plans/{plan['plan_id']}/verify").json()
    plan = _plan_of(verified, plan["plan_id"])
    assert plan["status"] == "NOT_RESOLVED"
    outcomes = {r["outcome"] for r in plan["verifications"][-1]["results"]}
    assert outcomes == {"pass", "fail"}
    assert any("NOT_RESOLVED" in w for w in verified["warnings"])


def test_verification_tool_failure_is_inconclusive(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Scenario 5: failed measurements prevent any verdict."""
    body = _investigate("Is the Windows Update service healthy?", service_name="wuauserv")
    details = [item for item in body["evidence"] if item["category"] == "service_details"]
    payload = _manual_worker_plan(details[0]["id"])
    payload["intended_state"] = "Windows Update service reports Running."
    payload["criteria"] = [
        {
            "description": "Service status reads Running.",
            "tool_name": "get_service_details",
            "tool_args": {"name": "wuauserv"},
            "path": "status.status",
            "op": "eq",
            "expected": "Running",
        }
    ]
    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans", json=payload
    ).json()["plans"][-1]
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    client.post(
        f"/api/plans/{plan['plan_id']}/interventions/manual",
        json={"description": "Started the service from services.msc."},
    )
    monkeypatch.setenv("FIELDROOK_FIXTURE_MISSING_SERVICES", "wuauserv")
    verified = client.post(f"/api/plans/{plan['plan_id']}/verify").json()
    plan = _plan_of(verified, plan["plan_id"])
    assert plan["status"] == "INCONCLUSIVE"
    assert plan["verifications"][-1]["results"][0]["outcome"] == "inconclusive"
    assert any("INCONCLUSIVE" in w for w in verified["warnings"])


def test_repeated_verify_never_executes() -> None:
    """Scenario 6: Confirm Fix re-measures; it cannot run actions."""
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_manual_worker_plan(worker_items[0]["id"]),
    ).json()["plans"][-1]
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    client.post(
        f"/api/plans/{plan['plan_id']}/interventions/manual",
        json={"description": "Checked the worker; looked fine."},
    )
    first = client.post(f"/api/plans/{plan['plan_id']}/verify").json()
    second = client.post(f"/api/plans/{plan['plan_id']}/verify").json()
    plan = _plan_of(second, plan["plan_id"])
    assert len(plan["verifications"]) == 2
    assert all(v["outcome"] == "VERIFIED_RESOLVED" for v in plan["verifications"])
    assert second["executions"] == []
    assert first["executions"] == []


def test_plan_persists_and_exports() -> None:
    """Scenario 7: plans survive reopen and export with outcomes."""
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_manual_worker_plan(worker_items[0]["id"]),
    ).json()["plans"][-1]
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    client.post(
        f"/api/plans/{plan['plan_id']}/interventions/manual",
        json={"description": "Restarted the worker by hand."},
    )
    client.post(f"/api/plans/{plan['plan_id']}/verify")
    fetched = client.get(f"/api/investigations/{body['investigation_id']}").json()
    plan = _plan_of(fetched, plan["plan_id"])
    assert plan["status"] == "VERIFIED_RESOLVED"
    assert len(plan["verifications"]) == 1
    report = client.get(
        f"/api/investigations/{body['investigation_id']}/export?format=markdown"
    )
    assert report.status_code == 200
    assert "## 15. Resolution plans" in report.text
    assert "VERIFIED_RESOLVED" in report.text
    assert "technician claim only" in report.text


def test_baseline_invalidates_pending_approval() -> None:
    """Scenario 8: new plan evidence voids an approval granted before it."""
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    created = client.post(
        f"/api/investigations/{body['investigation_id']}/proposals",
        json={"action_id": "recover_demo_worker", "target": "demo-worker", "reason": "Stale test."},
    )
    assert created.status_code == 200
    proposal_id = created.json()["proposals"][-1]["proposal_id"]
    approved = client.post(f"/api/proposals/{proposal_id}/approve")
    assert approved.status_code == 200
    token = approved.json()["approval_token"]

    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_worker_plan(worker_items[0]["id"]),
    ).json()["plans"][-1]
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    refused = client.post(
        f"/api/proposals/{proposal_id}/execute",
        json={"approval_token": token, "args": {}},
    )
    assert refused.status_code == 400
    assert "changed" in refused.json()["detail"].lower()


def test_plan_rejects_unknown_tool_and_evidence() -> None:
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    bad_tool = _manual_worker_plan(worker_items[0]["id"])
    bad_tool["criteria"][0]["tool_name"] = "format_drive"
    denied = client.post(
        f"/api/investigations/{body['investigation_id']}/plans", json=bad_tool
    )
    assert denied.status_code == 400
    bad_evidence = _manual_worker_plan("ev-999")
    denied = client.post(
        f"/api/investigations/{body['investigation_id']}/plans", json=bad_evidence
    )
    assert denied.status_code == 400
    bad_action = _worker_plan(worker_items[0]["id"])
    bad_action["action_id"] = "format_drive"
    denied = client.post(
        f"/api/investigations/{body['investigation_id']}/plans", json=bad_action
    )
    assert denied.status_code == 400


def test_unmeasurable_baseline_rejected() -> None:
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    payload = _manual_worker_plan(worker_items[0]["id"])
    payload["criteria"][0]["path"] = "no.such.path"
    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans", json=payload
    ).json()["plans"][-1]
    refused = client.post(f"/api/plans/{plan['plan_id']}/baseline")
    assert refused.status_code == 422


def test_verify_requires_baseline_and_intervention() -> None:
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    plan = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_manual_worker_plan(worker_items[0]["id"]),
    ).json()["plans"][-1]
    assert client.post(f"/api/plans/{plan['plan_id']}/verify").status_code == 400
    assert (
        client.post(
            f"/api/plans/{plan['plan_id']}/interventions/manual",
            json={"description": "Too early."},
        ).status_code
        == 400
    )
    client.post(f"/api/plans/{plan['plan_id']}/baseline")
    assert client.post(f"/api/plans/{plan['plan_id']}/verify").status_code == 400


def test_plan_template_rejects_unknown_action() -> None:
    assert client.get("/api/plans/template?action_id=format_drive").status_code == 400


def test_plan_mutations_reject_cross_origin() -> None:
    body = _investigate("The FieldRook demo worker is down.")
    worker_items = [item for item in body["evidence"] if item["category"] == "demo_worker"]
    evil = {"Origin": "https://evil.example"}
    refused = client.post(
        f"/api/investigations/{body['investigation_id']}/plans",
        json=_manual_worker_plan(worker_items[0]["id"]),
        headers=evil,
    )
    assert refused.status_code == 403
