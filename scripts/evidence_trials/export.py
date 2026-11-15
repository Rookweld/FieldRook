"""Reproduce public Evidence Trials from FieldRook's real fixture-only API.

Run after python -m eval.run with no --live. Nothing here executes a
corrective action: the worker trials use manual intervention claims and a
separate fixture-only remeasurement. No host telemetry is exported.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ["FIELDROOK_OFFLINE"] = "1"
os.environ["MODEL_API_KEY"] = ""
from eval.run import CASES, client  # noqa: E402 (fixture DB isolated by runner)

CASES_BY_ID = {case.id: case for case in CASES}
SELECTED = ("task-phantom", "resolve-manual-worker", "resolve-still-failing")
COPY = {
    "task-phantom": {
        "number": "01",
        "title": "The Five-Minute Phantom",
        "eyebrow": "Scheduled tasks / evidence before assumptions",
        "verdict": "CAUSE NOT VERIFIED",
        "tone": "uncertain",
        "story": "PowerShell windows flash every five minutes. A task matches that cadence, but matching a schedule is not proof of causation.",
        "takeaway": "A plausible suspect is a lead, not a verdict.",
    },
    "resolve-manual-worker": {
        "number": "02",
        "title": "The Measured Recovery",
        "eyebrow": "Recovery / measured state transition",
        "verdict": "VERIFIED_RESOLVED",
        "tone": "resolved",
        "story": "The demo worker reports failure. A technician claims an intervention, then FieldRook independently rechecks fixture measurements.",
        "takeaway": "The claim is recorded. Fresh evidence decides the outcome.",
    },
    "resolve-still-failing": {
        "number": "03",
        "title": "The Fix That Wasn't",
        "eyebrow": "Counterexample / verification over confidence",
        "verdict": "NOT_RESOLVED",
        "tone": "unresolved",
        "story": "The same initial failure and a reported intervention, but the status remains failed. FieldRook must reject the claimed fix.",
        "takeaway": "A successful-looking workflow must not overrule a failed measurement.",
    },
}


def check(response, label):
    if response.status_code != 200:
        raise RuntimeError(f"{label}: HTTP {response.status_code}: {response.text[:250]}")
    return response.json()


def with_env(env, fn):
    previous = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    try:
        return fn()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def safe_evidence(item):
    assert item["source"].startswith("tool:") and item["source"].endswith(":fixture")
    d = item["data"]
    summary = {"summary": d.get("summary", ""), "warnings": d.get("warnings", [])}
    if item["category"] == "scheduled_tasks":
        summary.update({
            "count": d.get("count"), "total_scanned": d.get("total_scanned"),
            "tasks": [
                {
                    "task_name": t.get("task_name"),
                    "state": t.get("state"),
                    "triggers": [
                        {"type": trig.get("type"), "repetition_interval": trig.get("repetition_interval")}
                        for trig in t.get("triggers", [])
                    ],
                    "actions": [
                        {"execute": a.get("execute"), "arguments": a.get("arguments"),
                         "working_directory": a.get("working_directory")}
                        for a in t.get("actions", [])
                    ],
                    "last_task_result": t.get("last_task_result"),
                    "last_run_succeeded": t.get("last_run_succeeded"),
                }
                for t in d.get("tasks", [])
                if t.get("task_name") in ("FieldRookDemoPhantom", "RookweldSync")
            ],
        })
    elif item["category"] == "event_log":
        summary["logs"] = [{"log": x.get("log"), "scanned": x.get("scanned"),
                            "matched": x.get("matched")} for x in d.get("logs", [])]
    elif item["category"] == "demo_worker":
        summary.update({"worker_id": d.get("worker_id"), "status": d.get("status"),
                        "heartbeat_age_s": d.get("heartbeat_age_s"),
                        "process_verified": d.get("process_verified")})
    else:
        raise RuntimeError("Unexpected public evidence category: " + str(item["category"]))
    return {
        "id": item["id"], "category": item["category"], "source": item["source"],
        "tool_name": item["tool_name"], "tool_args": item.get("tool_args") or {},
        "data": summary, "refresh_of": item.get("refresh_of"),
    }


def export_case(case_id, gauntlet):
    c = CASES_BY_ID[case_id]
    form = {"problem": c.problem, "use_fixtures": "true"}
    if c.service_name:
        form["service_name"] = c.service_name
    body = with_env(c.env, lambda: check(client.post("/api/investigations", data=form), case_id))
    assert body.get("uses_fixtures") is True
    assert body.get("analysis_mode") == "simulated"
    assert not body.get("executions")
    if case_id == "task-phantom":
        assert not body.get("proposals"), "Unverified task must not trigger action"
        verified_body = body
        verification = None
    else:
        usable = [item for item in body.get("evidence", []) if item.get("tool_name")]
        assert usable, "Missing initial measured worker evidence"
        tpl = check(client.get("/api/plans/template?action_id=recover_demo_worker"), "template")
        payload = {
            "evidence_ids": [usable[0]["id"]],
            "intended_state": tpl["intended_state"],
            "criteria": tpl["criteria"], "guidance": tpl["guidance"],
            "risks": tpl["risks"], "remediation_kind": "manual",
        }
        def plan_cycle():
            created = check(client.post(
                f"/api/investigations/{body['investigation_id']}/plans", json=payload
            ), "create manual plan")
            plan_id = created["plans"][-1]["plan_id"]
            baseline = check(client.post(f"/api/plans/{plan_id}/baseline"), "baseline")
            claimed = check(client.post(
                f"/api/plans/{plan_id}/interventions/manual",
                json={"description": "Synthetic technician claim: intervention completed. This is not proof."},
            ), "record manual claim")
            assert next(p for p in claimed["plans"] if p["plan_id"] == plan_id)["status"] == "INTERVENED"
            after = with_env(c.resolution_env_verify, lambda: check(
                client.post(f"/api/plans/{plan_id}/verify"), "verify fresh evidence"
            ))
            plan = next(p for p in after["plans"] if p["plan_id"] == plan_id)
            assert plan["status"] == c.expect_resolution, (plan["status"], c.expect_resolution)
            assert plan["verifications"]
            assert not after.get("executions"), "A manual demonstration must not execute actions"
            return baseline, after, plan
        baseline, verified_body, plan = with_env(c.env, plan_cycle)
        verdict = plan["verifications"][-1]
        before_map = plan.get("baseline_values") or {}
        verification = {
            "kind": "manual_intervention_claim",
            "intervention_proven": False,
            "intended_state": plan["intended_state"],
            "status": plan["status"],
            "criteria": [
                {
                    "description": crit["description"], "tool_name": crit["tool_name"],
                    "path": crit["path"], "operator": crit["op"], "expected": crit["expected"],
                    "baseline": before_map[crit["criterion_id"]],
                    "outcome": next(x["outcome"] for x in verdict["results"] if x["criterion_id"] == crit["criterion_id"]),
                    "observed": next(x["observed"] for x in verdict["results"] if x["criterion_id"] == crit["criterion_id"]),
                    "detail": next(x["detail"] for x in verdict["results"] if x["criterion_id"] == crit["criterion_id"]),
                    "before_evidence_id": next(x["before_evidence_id"] for x in verdict["results"] if x["criterion_id"] == crit["criterion_id"]),
                    "after_evidence_id": next(x["after_evidence_id"] for x in verdict["results"] if x["criterion_id"] == crit["criterion_id"]),
                }
                for crit in plan["criteria"]
            ],
            "after_evidence_ids": verdict["after_evidence_ids"],
            "uncertainties": verdict.get("uncertainties", []),
        }

    evidence = [safe_evidence(item) for item in verified_body.get("evidence", [])]
    ids = {e["id"] for e in evidence}
    assessment = verified_body.get("assessment") or {}
    facts = [{"statement": fact["statement"], "evidence_ids": fact.get("evidence_ids", [])}
             for fact in assessment.get("facts", [])]
    hypotheses = [{"title": cause["title"], "description": cause["description"],
                   "likelihood": cause.get("likelihood", "unknown"),
                   "evidence_ids": cause.get("evidence_ids", [])}
                  for cause in assessment.get("causes", [])]
    refs = [r for fact in facts for r in fact["evidence_ids"]]
    refs += [r for hypo in hypotheses for r in hypo["evidence_ids"]]
    if verification:
        for crit in verification["criteria"]:
            refs += [crit["before_evidence_id"], crit["after_evidence_id"]]
    assert set(refs) <= ids, "References must resolve to exported evidence"
    assert all(e["source"].endswith(":fixture") for e in evidence)
    timeline = [
        {"seq": e["seq"], "kind": e["kind"], "title": e["title"],
         "detail": e.get("detail", ""), "tool_name": e.get("tool_name"),
         "evidence_ids": e.get("evidence_ids", [])}
        for e in verified_body.get("activity", [])
        if e.get("kind") not in {"question", "troubleshoot_plan"}
    ]
    assert all(ref in ids for step in timeline for ref in step["evidence_ids"])
    row = COPY[case_id] | {
        "case_id": case_id, "question": c.problem, "reference": c.reference,
        "analysis_mode": body["analysis_mode"], "fixture_only": True,
        "model": body.get("model", "simulated"),
        "facts": facts, "hypotheses": hypotheses,
        "uncertainties": assessment.get("uncertainties", []),
        "missing_evidence": assessment.get("missing_evidence", []),
        "next_actions": assessment.get("next_actions", []),
        "summary": assessment.get("summary", ""),
        "evidence": evidence, "timeline": timeline, "verification": verification,
        "tool_calls_used": body.get("tool_calls_used"),
        "auto_executions": 0,
        "gauntlet": {"passed": True, "case_id": case_id, "detail": gauntlet["detail"]},
    }
    if case_id == "task-phantom":
        assert any("FieldRookDemoPhantom" in str(e["data"]) for e in evidence)
        assert not verification
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gauntlet", required=True, type=Path,
                        help="Completed fixture-only eval JSON generated by python -m eval.run")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs" / "evidence-trials" / "data" / "trials.json")
    args = parser.parse_args()
    report = json.loads(args.gauntlet.read_text(encoding="utf-8"))
    assert report["live_model_cases"] == 0, "The public export must be fixture-only"
    evaluated = [r for r in report["results"] if r["passed"] is not None]
    assert evaluated and all(r["passed"] is True for r in evaluated)
    by_id = {r["id"]: r for r in evaluated}
    assert all(by_id[k]["passed"] for k in SELECTED)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    payload = {
        "schema_version": 1,
        "source_commit": commit,
        "gauntlet": {
            "run_utc": report["created_at"], "evaluated": len(evaluated),
            "passed": sum(r["passed"] is True for r in evaluated), "live_model_cases": 0,
            "note": "Fixture and tool checks; not a measure of production model accuracy.",
        },
        "disclaimer": "Offline synthetic fixtures. Simulated inference. No production telemetry, customer data, autonomous action or live-model benchmark.",
        "cases": [export_case(k, by_id[k]) for k in SELECTED],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"EXPORT_OK: {len(payload['cases'])} trials, {payload['gauntlet']['passed']}/{payload['gauntlet']['evaluated']} checks, {args.output}")
    for case in payload["cases"]:
        print(f"  {case['case_id']}: {case['verdict']} / evidence={len(case['evidence'])} / timeline={len(case['timeline'])}")


if __name__ == "__main__":
    main()
