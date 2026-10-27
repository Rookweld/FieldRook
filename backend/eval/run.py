"""Gauntlet runner: deterministic fixture evals + capped live-model evals.

Usage (from backend/):
    python -m eval.run                  # fixture + tool cases (no key, CI-safe)
    python -m eval.run --live           # also live-model cases (needs MODEL_API_KEY)
    python -m eval.run --live --max-live-cases 2 --sleep-s 5

Results: backend/eval/results/<utc-timestamp>.json (gitignored) + console table.
Exit code is non-zero if any evaluated case fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_db_fd, _db_path = tempfile.mkstemp(prefix="fieldrook-gauntlet-", suffix=".db")
os.close(_db_fd)
os.environ["FIELDROOK_DB_PATH"] = _db_path
os.environ["FIELDROOK_FIXTURES"] = "always"
# Isolate the demo-worker state dir: the recovery precondition live-checks the
# real worker, so a healthy worker on the dev machine would (correctly) veto
# the fixture worker-failing proposal. Hermetic evals need their own dir.
_demo_state = tempfile.mkdtemp(prefix="fieldrook-gauntlet-demo-")
os.environ["FIELDROOK_DEMO_STATE"] = _demo_state

from app.config import load_settings  # noqa: E402
from app.tools.registry import ToolContext, execute_prepared, prepare_call  # noqa: E402
from eval.cases import CASES, TOOL_CASES, Case, ToolCase  # noqa: E402

import asyncio  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _assessment_text(assessment: dict) -> str:
    parts = [assessment.get("summary", ""), assessment.get("explanation", "")]
    for cause in assessment.get("causes", []):
        parts.append(cause.get("title", "") + " " + cause.get("description", ""))
    parts.extend(assessment.get("uncertainties", []))
    parts.extend(assessment.get("missing_evidence", []))
    return " ".join(parts).lower()


def _banned_claim(text: str, banned: str) -> bool:
    """Substring check with one refinement: bare 'proven' is overconfident,
    but hedged forms ('not proven', 'unproven', ...) are honest calibration
    and must not trip the check."""
    if banned != "proven":
        return banned in text
    cleaned = re.sub(
        r"unproven|not proven|n't proven|never proven|nothing proven|no ((?!doubt|question)[a-z\- ]){0,50}?proven",
        " ",
        text,
    )
    return re.search(r"\bproven\b", cleaned) is not None


def _check_citations(body: dict) -> list[str]:
    known = {item["id"] for item in body.get("evidence", [])}
    problems = []
    assessment = body.get("assessment") or {}
    for fact in assessment.get("facts", []):
        unknown = set(fact.get("evidence_ids", [])) - known
        if unknown:
            problems.append(f"fact cites unknown ids {sorted(unknown)}")
    for cause in assessment.get("causes", []):
        unknown = set(cause.get("evidence_ids", [])) - known
        if unknown:
            problems.append(f"cause {cause.get('title', '?')[:40]!r} cites unknown ids {sorted(unknown)}")
    for refresh in body.get("refreshes", []):
        refs = {refresh.get("old_evidence_id"), refresh.get("new_evidence_id")} - {None}
        unknown = refs - known
        if unknown:
            problems.append(f"refresh references unknown ids {sorted(unknown)}")
    for hit in body.get("contradictions", []):
        unknown = set(hit.get("evidence_ids", [])) - known
        if unknown:
            problems.append(f"contradiction cites unknown ids {sorted(unknown)}")
    return problems


def _check_followup_reuse(case: Case, body: dict) -> list[str]:
    """A follow-up answered by existing evidence must not re-collect it."""
    before = sum(1 for r in body.get("activity", []) if r.get("kind") == "tool_request")
    try:
        response = client.post(
            f"/api/investigations/{body['investigation_id']}/followup",
            json={"message": case.followup},
        )
    except Exception as exc:  # noqa: BLE001 - eval must report, not crash
        return [f"followup request failed: {exc}"]
    if response.status_code != 200:
        return [f"followup HTTP {response.status_code}"]
    after_body = response.json()
    after = sum(1 for r in after_body.get("activity", []) if r.get("kind") == "tool_request")
    new_calls = after - before
    if new_calls > case.followup_max_new_calls:
        return [f"followup made {new_calls} new tool calls (max {case.followup_max_new_calls})"]
    return []


def _check_reverify(case: Case, body: dict) -> list[str]:
    """Post a real reverify call: verdict, history, budget, authorization."""
    problems: list[str] = []
    candidates = [
        item for item in body.get("evidence", [])
        if item.get("category") == case.reverify_category and item.get("tool_name")
    ]
    if not candidates:
        return [f"no re-runnable {case.reverify_category} evidence to re-verify"]
    old = candidates[-1]
    old_snapshot = json.dumps(old.get("data"), sort_keys=True, default=str)
    calls_before = body.get("tool_calls_used", 0)
    proposals_before = len(body.get("proposals", []))
    saved_env = {key: os.environ.get(key) for key in case.reverify_env}
    os.environ.update(case.reverify_env)
    try:
        response = client.post(
            f"/api/investigations/{body['investigation_id']}/reverify",
            json={"evidence_id": old["id"]},
        )
    except Exception as exc:  # noqa: BLE001 - eval must report, not crash
        return [f"reverify request failed: {exc}"]
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if response.status_code != 200:
        return [f"reverify HTTP {response.status_code}: {response.text[:200]}"]
    after = response.json()
    refreshes = after.get("refreshes", [])
    if not refreshes:
        return ["reverify produced no refresh record"]
    refresh = refreshes[-1]
    if case.expect_verdict and refresh.get("verdict") != case.expect_verdict:
        problems.append(
            f"verdict {refresh.get('verdict')!r}, want {case.expect_verdict!r}"
        )
    by_id = {item["id"]: item for item in after.get("evidence", [])}
    kept = by_id.get(old["id"])
    if kept is None:
        problems.append("historical evidence item missing after reverify")
    elif json.dumps(kept.get("data"), sort_keys=True, default=str) != old_snapshot:
        problems.append("historical evidence data was modified by reverify")
    elif kept.get("collected_at") != old.get("collected_at"):
        problems.append("historical collected_at was modified by reverify")
    new_id = refresh.get("new_evidence_id")
    if new_id and by_id.get(new_id, {}).get("refresh_of") != old["id"]:
        problems.append("new item is not linked to its historical item")
    if after.get("tool_calls_used", 0) != calls_before + 1:
        problems.append(
            f"reverify cost {after.get('tool_calls_used', 0) - calls_before} calls, want exactly 1"
        )
    if len(after.get("proposals", [])) != proposals_before:
        problems.append("reverify changed the proposal set (authorization boundary)")
    problems.extend(f"after reverify: {p}" for p in _check_citations(after))
    return problems


def _check_resolution(case: Case, body: dict) -> list[str]:
    """Drive plan -> baseline -> manual claim -> verify through the API."""
    problems: list[str] = []
    usable = [item for item in body.get("evidence", []) if item.get("tool_name")]
    if not usable:
        return ["no tool-backed evidence to plan from"]
    if case.resolution_use_template:
        template_response = client.get(
            f"/api/plans/template?action_id={case.resolution_use_template}"
        )
        if template_response.status_code != 200:
            return [f"template HTTP {template_response.status_code}"]
        template = template_response.json()
        criteria = template["criteria"]
        intended = template["intended_state"]
        guidance, risks = template["guidance"], template["risks"]
    else:
        criteria = list(case.resolution_criteria)
        intended = "Resolve the reported problem (gauntlet)."
        guidance, risks = "Gauntlet flow.", "None."
    if not criteria:
        return ["no criteria for resolution plan"]
    payload: dict = {
        "evidence_ids": [usable[0]["id"]],
        "intended_state": intended,
        "criteria": criteria,
        "guidance": guidance,
        "risks": risks,
        "remediation_kind": case.resolution_kind or "manual",
    }
    if case.resolution_action:
        payload["action_id"] = case.resolution_action
        payload["target"] = "demo-worker"
    proposals_before = len(body.get("proposals", []))
    saved_env = {key: os.environ.get(key) for key in case.env}
    os.environ.update(case.env)
    try:
        created = client.post(
            f"/api/investigations/{body['investigation_id']}/plans", json=payload
        )
        if created.status_code != 200:
            return [f"plan HTTP {created.status_code}: {created.text[:200]}"]
        plan_id = created.json()["plans"][-1]["plan_id"]
        baselined = client.post(f"/api/plans/{plan_id}/baseline")
        if baselined.status_code != 200:
            return [f"baseline HTTP {baselined.status_code}: {baselined.text[:200]}"]
        plan = next(p for p in baselined.json()["plans"] if p["plan_id"] == plan_id)
        if not any(v is not None for v in plan["baseline_values"].values()):
            return ["baseline measured nothing"]
        claimed = client.post(
            f"/api/plans/{plan_id}/interventions/manual",
            json={"description": "Gauntlet technician claim (not proof)."},
        )
        if claimed.status_code != 200:
            return [f"manual HTTP {claimed.status_code}"]
        if next(p for p in claimed.json()["plans"] if p["plan_id"] == plan_id)["status"] != "INTERVENED":
            return ["manual claim changed more than the intervention record"]
        verify_saved = {key: os.environ.get(key) for key in case.resolution_env_verify}
        os.environ.update(case.resolution_env_verify)
        try:
            verified = client.post(f"/api/plans/{plan_id}/verify")
        finally:
            for key, value in verify_saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception as exc:  # noqa: BLE001 - eval must report, not crash
        return [f"resolution flow failed: {exc}"]
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if verified.status_code != 200:
        return [f"verify HTTP {verified.status_code}: {verified.text[:200]}"]
    after = verified.json()
    plan = next(p for p in after["plans"] if p["plan_id"] == plan_id)
    if case.expect_resolution and plan["status"] != case.expect_resolution:
        problems.append(f"resolution {plan['status']!r}, want {case.expect_resolution!r}")
    if not plan["verifications"]:
        problems.append("verify produced no verification record")
    if len(after.get("proposals", [])) != proposals_before:
        problems.append("resolution flow changed the proposal set")
    if after.get("executions"):
        problems.append("resolution flow executed an action")
    problems.extend(f"after verify: {p}" for p in _check_citations(after))
    return problems


def _check_memory_flow(case: Case, body: dict) -> list[str]:
    """Record inv1 to memory, then match/recheck from a second incident."""
    problems: list[str] = []
    entry_id: str | None = None
    saved_env = {key: os.environ.get(key) for key in case.env}
    os.environ.update(case.env)
    try:
        inv1 = body["investigation_id"]
        if case.memory_resolve:
            usable = [i for i in body.get("evidence", []) if i.get("tool_name")]
            if not usable:
                return ["no tool-backed evidence to resolve"]
            template = client.get("/api/plans/template?action_id=recover_demo_worker")
            if template.status_code != 200:
                return ["memory setup: no template"]
            tpl = template.json()
            created = client.post(
                f"/api/investigations/{inv1}/plans",
                json={
                    "evidence_ids": [usable[0]["id"]],
                    "intended_state": tpl["intended_state"],
                    "criteria": tpl["criteria"],
                    "guidance": "Gauntlet.", "risks": "None.",
                    "remediation_kind": "manual",
                },
            )
            if created.status_code != 200:
                return [f"memory setup plan HTTP {created.status_code}"]
            plan_id = created.json()["plans"][-1]["plan_id"]
            if client.post(f"/api/plans/{plan_id}/baseline").status_code != 200:
                return ["memory setup baseline failed"]
            client.post(
                f"/api/plans/{plan_id}/interventions/manual",
                json={"description": "Gauntlet fix."},
            )
            verify_saved = {k: os.environ.get(k) for k in case.memory_verify_env}
            os.environ.update(case.memory_verify_env)
            try:
                verified = client.post(f"/api/plans/{plan_id}/verify")
            finally:
                for key, value in verify_saved.items():
                    os.environ.pop(key, None) if value is None else os.environ.update({key: value})
            if verified.status_code != 200:
                return ["memory setup verify failed"]
        recorded = client.post(f"/api/investigations/{inv1}/knowledge", json={})
        if recorded.status_code not in (200, 201):
            return [f"record HTTP {recorded.status_code}: {recorded.text[:200]}"]
        entry_id = recorded.json()["entry_id"]
    except Exception as exc:  # noqa: BLE001 - eval must report, not crash
        return [f"memory setup failed: {exc}"]
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    try:
        second_saved = {k: os.environ.get(k) for k in case.memory_second_env}
        os.environ.update(case.memory_second_env)
        try:
            second = client.post(
                "/api/investigations",
                data={
                    "problem": case.memory_second_problem or case.problem,
                    "force_fixtures": "true",
                },
            )
        finally:
            for key, value in second_saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        if second.status_code != 200:
            return [f"memory second investigation HTTP {second.status_code}"]
        inv2 = second.json()["investigation_id"]
        matches = client.get(
            f"/api/investigations/{inv2}/knowledge/matches"
        ).json()["matches"]
        for match in matches:
            if client.get(f"/api/knowledge/{match['entry']['entry_id']}").status_code != 200:
                problems.append("matched entry id does not resolve")
        if not case.memory_recheck:
            mine = [m for m in matches if m["entry"]["entry_id"] == entry_id]
            if not mine:
                return ["recorded entry did not match the repeat incident"]
            match = mine[0]
            signals = {s["signal"] for s in match["signals"]}
            for want in case.memory_expect_signals:
                if want not in signals:
                    problems.append(f"missing match signal {want!r} (have {sorted(signals)})")
            if not match["signals"]:
                problems.append("match has no explanatory signals")
            blob = " ".join(match["differences"]).lower()
            for want in case.memory_expect_differences:
                if want.lower() not in blob:
                    problems.append(f"differences omit {want!r}")
            if case.memory_expect_outcome and match["entry"]["outcome"] != case.memory_expect_outcome:
                problems.append(
                    f"matched outcome {match['entry']['outcome']!r}, "
                    f"want {case.memory_expect_outcome!r}"
                )
        if case.memory_recheck:
            recheck_saved = {k: os.environ.get(k) for k in case.memory_recheck_env}
            os.environ.update(case.memory_recheck_env)
            try:
                rechecked = client.post(
                    f"/api/investigations/{inv2}/knowledge/{entry_id}/recheck"
                )
            finally:
                for key, value in recheck_saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            if rechecked.status_code != 200:
                return [f"recheck HTTP {rechecked.status_code}: {rechecked.text[:200]}"]
            checks = rechecked.json().get("regression_checks", [])
            if not checks:
                problems.append("recheck produced no regression check")
            elif case.memory_expect_recheck and checks[-1]["outcome"] != case.memory_expect_recheck:
                problems.append(
                    f"recheck {checks[-1]['outcome']!r}, want {case.memory_expect_recheck!r}"
                )
            kept = client.get(f"/api/knowledge/{entry_id}").json()
            if kept["outcome"] == "REGRESSION":
                problems.append("recheck overwrote the historical outcome")
            problems.extend(
                f"after recheck: {p}" for p in _check_citations(rechecked.json())
            )
    except Exception as exc:  # noqa: BLE001 - eval must report, not crash
        problems.append(f"memory flow failed: {exc}")
    finally:
        if entry_id:
            client.delete(f"/api/knowledge/{entry_id}")
    return problems


def run_case(case: Case) -> dict:
    saved_env = {key: os.environ.get(key) for key in case.env}
    os.environ.update(case.env)
    form: dict[str, str] = {"problem": case.problem}
    if case.service_name:
        form["service_name"] = case.service_name
    if case.use_fixtures:
        form["use_fixtures"] = "true"
    started = time.perf_counter()
    try:
        response = client.post("/api/investigations", data=form)
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    latency_s = round(time.perf_counter() - started, 2)
    if case.id == "svc-bogus-name":
        passed = response.status_code == 400
        return {
            "id": case.id, "category": case.category, "passed": passed,
            "latency_s": latency_s, "detail": f"HTTP {response.status_code} (want 400)",
            "failures": [] if passed else [f"HTTP {response.status_code}"],
        }
    failures: list[str] = []
    if response.status_code != 200:
        return {
            "id": case.id, "category": case.category, "passed": False,
            "latency_s": latency_s, "detail": f"HTTP {response.status_code}",
            "failures": [f"HTTP {response.status_code}: {response.text[:200]}"],
        }
    body = response.json()
    tools_used = {r["tool_name"] for r in body.get("activity", []) if r.get("tool_name")}
    if case.must_use_all and not set(case.must_use_all) <= tools_used:
        failures.append(f"missing tools {sorted(set(case.must_use_all) - tools_used)}")
    if case.must_use_any and not (set(case.must_use_any) & tools_used):
        failures.append(f"none of {sorted(case.must_use_any)} used (used {sorted(tools_used)})")
    swept = set(case.forbid_tools) & tools_used
    if swept:
        failures.append(f"unrelated sweep tools used {sorted(swept)} (used {sorted(tools_used)})")
    if case.followup:
        failures.extend(_check_followup_reuse(case, body))
    if case.expect_contradiction and not body.get("contradictions"):
        failures.append("expected a contradiction record, got none")
    if case.reverify_category:
        failures.extend(_check_reverify(case, body))
    if case.resolution_kind:
        failures.extend(_check_resolution(case, body))
    if case.memory_second_problem:
        failures.extend(_check_memory_flow(case, body))
    if case.max_tool_calls:
        # The runner's own reverify post costs one call; budget it too.
        total = body.get("tool_calls_used", 0) + (1 if case.reverify_category else 0)
        if total > case.max_tool_calls:
            failures.append(f"used {total} tool calls (max {case.max_tool_calls})")
    proposals = body.get("proposals", [])
    if case.expect_proposal and not proposals:
        failures.append("expected a proposal, got none")
    if case.forbid_proposal and proposals:
        failures.append(f"unexpected proposals {[p['proposal_id'] for p in proposals]}")
    assessment = body.get("assessment")
    if assessment is None:
        failures.append("no assessment produced")
        text = ""
    else:
        text = _assessment_text(assessment)
        if case.require_uncertainty and not (
            assessment.get("uncertainties") or assessment.get("missing_evidence")
        ):
            failures.append("no uncertainties/missing-evidence recorded")
        if case.must_mention_any and not any(s in text for s in case.must_mention_any):
            failures.append(f"mentions none of {list(case.must_mention_any)}")
        for banned in case.forbid_mention:
            if _banned_claim(text, banned):
                failures.append(f"forbidden claim language {banned!r}")
    failures.extend(_check_citations(body))
    tool_requests = sum(1 for r in body.get("activity", []) if r.get("kind") == "tool_request")
    detail = (
        f"tools={sorted(tools_used)} calls={tool_requests} "
        f"proposals={len(proposals)} mode={body.get('analysis_mode')}"
    )
    if body.get("contradictions"):
        detail += f" contradictions={len(body['contradictions'])}"
    if case.reverify_category:
        detail += f" reverify={case.expect_verdict or '?'}"
    if case.resolution_kind:
        detail += f" resolution={case.expect_resolution or '?'}"
    if case.memory_second_problem:
        detail += " memory=flow"
    result = {
        "id": case.id,
        "category": case.category,
        "passed": not failures,
        "latency_s": latency_s,
        "detail": detail,
        "failures": failures,
        "reference": case.reference,
    }
    if failures:
        # Compact failure context so live-model verdicts can be audited
        # honestly (substring checks cannot show their own evidence).
        result["context"] = text[:1200]
    return result


def run_tool_case(case: ToolCase) -> dict:
    settings = load_settings()
    spec, args = prepare_call(case.tool, case.args)
    output, _ = asyncio.run(
        execute_prepared(spec, args, ToolContext(settings=settings, use_fixtures=True))
    )
    failures: list[str] = []
    if case.expect_error and output.error is None:
        failures.append("expected an error output, got success")
    if not case.expect_error and output.error is not None:
        failures.append(f"unexpected error: {output.error}")
    for key, want in case.expect_contains.items():
        got = (output.data or {}).get(key)
        if got != want:
            failures.append(f"{key}={got!r}, want {want!r}")
    return {
        "id": case.id, "category": "error-codes" if case.id.startswith("err-") else "robustness",
        "passed": not failures, "latency_s": 0.0,
        "detail": f"error={output.error!r}" if output.error else f"data={output.data}",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FieldRook diagnostic gauntlet")
    parser.add_argument("--live", action="store_true", help="run live-model cases (needs MODEL_API_KEY)")
    parser.add_argument("--max-live-cases", type=int, default=3)
    parser.add_argument("--sleep-s", type=float, default=2.0)
    parser.add_argument("--results-dir", default=str(Path(__file__).resolve().parent / "results"))
    args = parser.parse_args()

    live_key = os.environ.get("MODEL_API_KEY") or load_settings().model_api_key
    if args.live and not live_key:
        print("LIVE mode requested but no MODEL_API_KEY resolves (env or .env). Aborting.")
        return 2

    results: list[dict] = []
    live_run = 0
    for case in CASES:
        if not case.live_model:
            os.environ["MODEL_API_KEY"] = ""
            results.append(run_case(case))
        elif args.live and live_run < args.max_live_cases:
            os.environ["MODEL_API_KEY"] = live_key  # restore the real key
            if live_run:
                time.sleep(args.sleep_s)
            live_run += 1
            results.append(run_case(case))
        else:
            results.append({
                "id": case.id, "category": case.category, "passed": None,
                "latency_s": 0.0, "detail": "skipped (live cap or --live not given)",
                "failures": [], "reference": case.reference,
            })
    os.environ["MODEL_API_KEY"] = ""
    for tool_case in TOOL_CASES:
        results.append(run_tool_case(tool_case))

    evaluated = [r for r in results if r["passed"] is not None]
    passed = [r for r in evaluated if r["passed"]]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": stamp,
        "live_model_cases": live_run,
        "usage_note": "Per-call token counts are not exposed by the provider responses; "
        "latency and tool-call counts are recorded instead.",
        "results": results,
    }
    out_path = out_dir / f"{stamp}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'CASE':28} {'RESULT':8} {'LAT(s)':7} DETAIL")
    for item in results:
        verdict = "SKIP" if item["passed"] is None else ("PASS" if item["passed"] else "FAIL")
        print(f"{item['id']:28} {verdict:8} {item['latency_s']:7} {item['detail']}")
        for failure in item["failures"]:
            print(f"  - {failure}")
    print(f"\n{evaluated and len(passed)}/{len(evaluated)} evaluated cases passed "
          f"({live_run} live-model). Results: {out_path}")
    return 0 if len(passed) == len(evaluated) else 1


if __name__ == "__main__":
    raise SystemExit(main())
