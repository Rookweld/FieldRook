"""M018 blind challenge runner.

One model per process (fresh DB + demo state each time):
`python eval/challenge/run_challenge.py --model qwen3:4b`.

Environment: FIELDROOK_OFFLINE=1 (no cloud calls), fixture diagnostics,
loopback-only local model. Results + de-identified transcripts go to
eval/results/challenge/<stamp>/; grading files are coded so the human
grade stays blind until scores are recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

_SAVED_MODEL_KEY = os.environ.get("MODEL_API_KEY", "")

os.environ["FIELDROOK_OFFLINE"] = "1"
os.environ["MODEL_API_KEY"] = ""
os.environ["FIELDROOK_FIXTURES"] = "always"
os.environ["FIELDROOK_FIXTURE_WORKER"] = "failing"
os.environ.pop("FIELDROOK_FIXTURE_WORKER_STATE", None)
os.environ["FIELDROOK_DB_PATH"] = str(
    Path(tempfile.mkdtemp(prefix="fieldrook-challenge-")) / "challenge.db"
)
os.environ["FIELDROOK_DEMO_STATE"] = tempfile.mkdtemp(prefix="fieldrook-challenge-demo-")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from eval.challenge.heldout_scenarios import HELDOUT_SCENARIOS  # noqa: E402
from eval.challenge.scenarios import SCENARIOS, Scenario  # noqa: E402
from eval.challenge.simulator import evaluate, render_transcript, run_scenario  # noqa: E402


def run_recovery_flow(client: TestClient, inv_id: str) -> dict:
    """Technician-driven M008 Confirm Fix on the demo worker.

    The runner acts as the technician: a REAL worker subprocess is started
    and failed, then plan from the registered template, baseline, propose
    -> approve -> execute the registered recovery, link, verify — all
    measured against live reads (fixtures suspended for this flow only).
    Returns ok + detail; the model is graded separately on whether it
    pointed at the worker.
    """
    import subprocess
    import sys
    import time as _time

    from app.actions import demo_worker

    previous_fixtures = os.environ.get("FIELDROOK_FIXTURES", "always")
    os.environ["FIELDROOK_FIXTURES"] = "never"  # live worker reads
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            [sys.executable, str(demo_worker.worker_script())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        deadline = _time.time() + 20
        while _time.time() < deadline:
            if demo_worker.read_health().get("status") == "healthy":
                break
            _time.sleep(0.5)
        else:
            return {"ok": False, "detail": "worker subprocess did not become healthy"}
        demo_worker.write_control("failing")
        deadline = _time.time() + 20
        while _time.time() < deadline:
            if demo_worker.read_health().get("status") == "failed":
                break
            _time.sleep(0.5)
        else:
            return {"ok": False, "detail": "worker did not report failed"}
        template = client.get(
            "/api/plans/template", params={"action_id": "recover_demo_worker"}
        )
        assert template.status_code == 200, template.text[:200]
        draft = template.json()
        state = client.get(f"/api/investigations/{inv_id}").json()
        worker_evidence = [
            e["id"] for e in state.get("evidence", [])
            if e.get("category") == "demo_worker" or e.get("tool_name") == "get_demo_worker_health"
        ]
        if not worker_evidence:
            return {
                "ok": False,
                "detail": "no demo-worker evidence collected; cannot ground the plan",
            }
        created = client.post(
            f"/api/investigations/{inv_id}/plans",
            json={
                "problem": "Demo worker keeps failing.",
                "evidence_ids": worker_evidence,
                "intended_state": draft.get(
                    "intended_state", "Demo worker reports healthy."
                ),
                "criteria": draft.get("criteria", []),
                "guidance": "Approve and run the registered recovery, then verify.",
                "risks": "None beyond the demo worker's own state directory.",
                "remediation_kind": "action",
                "action_id": "recover_demo_worker",
                "target": "demo-worker",
            },
        )
        assert created.status_code == 200, created.text[:300]
        plan_id = created.json()["plans"][-1]["plan_id"]
        baseline = client.post(f"/api/plans/{plan_id}/baseline")
        assert baseline.status_code == 200, baseline.text[:300]
        proposed = client.post(
            f"/api/investigations/{inv_id}/proposals",
            json={
                "action_id": "recover_demo_worker",
                "target": "demo-worker",
                "reason": "Challenge technician: worker unhealthy, recovery registered.",
            },
        )
        assert proposed.status_code == 200, proposed.text[:300]
        proposal_id = proposed.json()["proposals"][-1]["proposal_id"]
        approved = client.post(f"/api/proposals/{proposal_id}/approve")
        assert approved.status_code == 200, approved.text[:300]
        token = approved.json()["approval_token"]
        executed = client.post(
            f"/api/proposals/{proposal_id}/execute",
            json={"approval_token": token, "args": {}},
        )
        assert executed.status_code == 200, executed.text[:300]
        execution_id = executed.json()["execution_id"]
        linked = client.post(
            f"/api/plans/{plan_id}/interventions/link-execution",
            json={"execution_id": execution_id},
        )
        assert linked.status_code == 200, linked.text[:300]
        verified = client.post(f"/api/plans/{plan_id}/verify")
        assert verified.status_code == 200, verified.text[:300]
        plan = verified.json()["plans"][-1]
        status = plan.get("status")
        ok = status == "VERIFIED_RESOLVED"
        return {
            "ok": ok,
            "detail": f"plan {plan_id} -> {status}",
            "status": status,
        }
    except Exception as exc:  # noqa: BLE001 - recovery failure is a finding
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        os.environ["FIELDROOK_FIXTURES"] = previous_fixtures
        if proc is not None and proc.poll() is None:
            demo_worker.terminate_verified_worker(proc.pid)
            proc.wait(timeout=15)


def grade_code(model: str, scenario_id: str, stamp: str) -> str:
    digest = hashlib.sha256(f"{stamp}:{model}:{scenario_id}".encode()).hexdigest()
    return f"grade-{digest[:8]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="FieldRook M018 blind challenge")
    parser.add_argument("--model", required=True, help="local model name (e.g. qwen3:4b)")
    parser.add_argument("--provider", default="local")
    parser.add_argument("--scenarios", default="", help="comma-separated IDs (default: all)")
    parser.add_argument("--suite", default="main", choices=["main", "heldout", "all"],
                        help="M019: main = original 20 (comparison baseline); heldout = 6 unseen cases")
    parser.add_argument("--url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--vision", action="store_true", help="enable local vision flag")
    parser.add_argument("--max-turns", type=int, default=None, help="cap simulator turns per scenario")
    parser.add_argument("--num-gpu", type=int, default=None, help="force GPU layer count (0 = CPU-only)")
    parser.add_argument("--live", action="store_true",
                        help="allow cloud provider (requires MODEL_API_KEY; never default)")
    parser.add_argument("--results-dir", default=None)
    args = parser.parse_args()

    if args.provider == "meta" and not args.live:
        print("refusing cloud provider without --live (explicit authorization required)")
        return 2
    if args.live:
        from app.config import load_settings

        os.environ["FIELDROOK_OFFLINE"] = "0"
        if _SAVED_MODEL_KEY:
            os.environ["MODEL_API_KEY"] = _SAVED_MODEL_KEY
        else:
            # Let the project .env value load (blanking would block it).
            os.environ.pop("MODEL_API_KEY", None)
        if not load_settings().model_api_key:
            print("live run needs MODEL_API_KEY (environment or project .env)")
            return 2
        print("*** LIVE cloud evaluation: real Muse Spark calls ***")

    os.environ["FIELDROOK_LOCAL_MODEL_URL"] = args.url
    os.environ["FIELDROOK_LOCAL_MODEL_NAME"] = args.model
    os.environ["FIELDROOK_LOCAL_MODEL_VISION"] = "1" if args.vision else "0"
    if args.num_gpu is not None:
        os.environ["FIELDROOK_LOCAL_NUM_GPU"] = str(args.num_gpu)

    wanted = {s.strip() for s in args.scenarios.split(",") if s.strip()}
    pool: list[Scenario] = list(SCENARIOS)
    if args.suite == "heldout":
        pool = list(HELDOUT_SCENARIOS)
    elif args.suite == "all":
        pool = list(SCENARIOS) + list(HELDOUT_SCENARIOS)
    selected = [s for s in pool if not wanted or s.id in wanted]
    if not selected:
        print("no scenarios selected")
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.results_dir or Path(__file__).resolve().parent.parent / "results" / "challenge" / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    model_tag = args.model.replace(":", "-")

    print(f"challenge: model={args.model} provider={args.provider} suite={args.suite} scenarios={len(selected)}")
    sys.stdout.flush()

    results: list[dict] = []
    mapping: dict[str, dict] = {}
    for scenario in selected:
        started = time.monotonic()
        entry: dict = {"id": scenario.id, "title": scenario.title}
        try:
            run = run_scenario(client, scenario, args.provider, args.max_turns)
            recovery = None
            if scenario.recovery_flow:
                recovery = run_recovery_flow(client, run["investigation_id"])
                run["recovery"] = recovery
            final = client.get(f"/api/investigations/{run['investigation_id']}").json()
            checks = evaluate(scenario, run, final, recovery)
            entry.update(
                {
                    "ok": True,
                    "turns": run["turns"],
                    "stalled": run["stalled"],
                    "wall_s": run["wall_s"],
                    "model_calls": run["model_calls"],
                    "checks": checks,
                    "passed": sum(1 for c in checks if c["passed"]),
                    "total": len(checks),
                    "deliveries": run["deliveries"],
                    "recovery": recovery,
                    "intake_latency_s": run.get("intake_latency_s", 0.0),
                    "withheld_repeats": run.get("withheld_repeats", 0),
                    "stall_notes": run.get("stall_notes", 0),
                    "unsafe_flags": run.get("unsafe_flags", 0),
                    "hyp_revisions": run.get("hyp_revisions", 0),
                }
            )
            transcript = render_transcript(scenario, run, checks)
            entry["questions"] = len(
                {q["id"] for rec in run["records"] for q in rec.questions}
            )
            entry["unusable_tasks"] = sum(
                1
                for rec in run["records"]
                for w in rec.warnings
                if "no usable output" in w
            )
            code = grade_code(args.model, scenario.id, stamp)
            (out_dir / f"{code}.md").write_text(transcript, encoding="utf-8")
            mapping[code] = {"model": args.model, "scenario": scenario.id}
            entry["grade_file"] = f"{code}.md"
        except Exception as exc:  # noqa: BLE001 - one scenario must not kill the run
            entry.update(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace": traceback.format_exc(limit=5),
                    "wall_s": round(time.monotonic() - started, 1),
                }
            )
        results.append(entry)
        status = (
            f"{entry.get('passed', 0)}/{entry.get('total', 0)} checks"
            if entry.get("ok")
            else f"ERROR {entry.get('error')}"
        )
        print(
            f"  {scenario.id:24} {status} "
            f"turns={entry.get('turns', '-')} wall={entry.get('wall_s', '?')}s "
            f"calls={entry.get('model_calls', '?')} "
            f"q={entry.get('questions', '?')} unusable={entry.get('unusable_tasks', '?')} "
            f"withheld={entry.get('withheld_repeats', '?')} "
            f"unsafe={entry.get('unsafe_flags', '?')} stall={entry.get('stall_notes', '?')}",
            flush=True,
        )

    (out_dir / f"mapping-{model_tag}.json").write_text(
        json.dumps(
            {
                "created_at": stamp,
                "model": args.model,
                "provider": args.provider,
                "mapping": mapping,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary = {
        "created_at": stamp,
        "model": args.model,
        "provider": args.provider,
        "suite": args.suite,
        "num_gpu": args.num_gpu,
        "results": [
            {k: v for k, v in entry.items() if k != "trace"} for entry in results
        ],
    }
    (out_dir / f"summary-{model_tag}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    ok_runs = sum(1 for e in results if e.get("ok"))
    all_pass = sum(e.get("passed", 0) for e in results)
    all_total = sum(e.get("total", 0) for e in results)
    print(f"\n{ok_runs}/{len(results)} scenarios ran; {all_pass}/{all_total} checks passed.")
    print(f"results: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
