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
        r"unproven|not proven|n't proven|never proven|nothing proven|no \w+ proven",
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
    result = {
        "id": case.id,
        "category": case.category,
        "passed": not failures,
        "latency_s": latency_s,
        "detail": f"tools={sorted(tools_used)} calls={tool_requests} "
        f"proposals={len(proposals)} mode={body.get('analysis_mode')}",
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
