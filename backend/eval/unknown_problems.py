"""M016 unknown-problem evaluation: adaptability on unfamiliar cases.

Twelve deterministic offline cases (simulated provider, fixture tools) that
probe whether FieldRook behaves like a troubleshooting partner on problems
outside its prepared fixtures: clarifying questions, remote-target honesty,
hypothesis revision, graceful blocking, and measured (never assumed)
verification. Each case returns (passed, failures, detail).
"""

from __future__ import annotations

import os
from typing import Any, Callable

CaseFn = Callable[[Any], tuple[bool, list[str], str]]

CASES: list[tuple[str, str, str, CaseFn]] = []


def unknown_case(case_id: str, category: str, reference: str) -> Callable[[CaseFn], CaseFn]:
    def decorate(fn: CaseFn) -> CaseFn:
        CASES.append((case_id, category, reference, fn))
        return fn

    return decorate


# ---------------------------------------------------------------------------
# Shared assertions
# ---------------------------------------------------------------------------


def _tools_used(body: dict) -> set[str]:
    return {r["tool_name"] for r in body.get("activity", []) if r.get("tool_name")}


def _check_citations(body: dict) -> list[str]:
    """Every evidence reference must resolve to collected evidence."""
    known = {item["id"] for item in body.get("evidence", [])}
    bad: list[str] = []

    def check(ids: object, where: str) -> None:
        for eid in ids if isinstance(ids, list) else []:
            if eid not in known:
                bad.append(f"{where} cites unknown {eid}")

    assessment = body.get("assessment") or {}
    for fact in assessment.get("facts", []):
        check(fact.get("evidence_ids"), "fact")
    for cause in assessment.get("causes", []):
        check(cause.get("evidence_ids"), "cause")
    for step in assessment.get("next_steps", []):
        check(step.get("evidence_ids"), "runbook")
    for hyp in body.get("hypotheses", []):
        check(hyp.get("supporting_evidence_ids"), "hypothesis-support")
        check(hyp.get("contradicting_evidence_ids"), "hypothesis-contra")
    plan = body.get("plan") or {}
    for step in plan.get("steps", []):
        check(step.get("evidence_ids"), "plan-step")
    return bad


def _check(predicate: bool, failures: list[str], message: str) -> None:
    if not predicate:
        failures.append(message)


def _investigate(client: Any, problem: str, **extra: Any) -> dict:
    data: dict[str, Any] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200, response.text
    return response.json()


def _turn(client: Any, inv_id: str, text: str, **extra: Any) -> dict:
    data: dict[str, Any] = {"text": text}
    data.update(extra)
    response = client.post(f"/api/investigations/{inv_id}/turn", data=data)
    assert response.status_code == 200, response.text
    return response.json()


def _check_remote_guards(body: dict, failures: list[str]) -> None:
    _check(body.get("tool_calls_used") == 0, failures, "remote target must run zero host tools")
    host_items = [
        item for item in body.get("evidence", [])
        if str(item.get("source", "")).startswith("tool:")
    ]
    _check(not host_items, failures, f"remote target must collect no host evidence, got {len(host_items)}")
    plan = body.get("plan") or {}
    kinds = {step.get("kind") for step in plan.get("steps", [])}
    _check("AUTOMATED_READ_ONLY" not in kinds, failures, "remote plan must not offer automated host checks")
    _check(bool(body.get("questions")), failures, "remote case must ask at least one question")


# ---------------------------------------------------------------------------
# The twelve cases
# ---------------------------------------------------------------------------


@unknown_case(
    "unknown-office-error-code", "unfamiliar",
    "Excel fails with 0x80070005: the code is decoded, questions follow, nothing is invented.",
)
def case_office_error_code(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "Excel fails with 0x80070005 when opening a file from email.")
    _check("interpret_error_code" in _tools_used(body), failures, "error code was not decoded")
    decoded = [i for i in body.get("evidence", []) if i.get("tool_name") == "interpret_error_code"]
    _check(bool(decoded) and decoded[0].get("error") is None, failures, "decode evidence missing/failed")
    _check(bool(body.get("hypotheses")), failures, "no hypotheses tracked")
    _check(bool(body.get("plan", {}).get("steps")), failures, "no plan steps")
    _check(
        all(c.get("likelihood") in ("medium", "low") for c in (body.get("assessment") or {}).get("causes", [])),
        failures, "simulated causes must never claim high likelihood",
    )
    failures.extend(_check_citations(body))
    detail = f"tools={sorted(_tools_used(body))} hyps={len(body.get('hypotheses', []))}"
    return (not failures, failures, detail)


@unknown_case(
    "teams-file-access", "unfamiliar",
    "Excel-over-Teams failure on another machine: zero host tools, question-first.",
)
def case_teams_file_access(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(
        client, "Excel won't open this file from Teams. It started happening this morning.",
        target="remote",
    )
    _check_remote_guards(body, failures)
    _check(body.get("stage") == "CLARIFYING", failures, f"expected CLARIFYING, got {body.get('stage')}")
    failures.extend(_check_citations(body))
    return (not failures, failures, f"questions={len(body.get('questions', []))}")


@unknown_case(
    "printer-other-laptop", "unfamiliar",
    "Printer unavailable on a separate laptop: honest remote handling, machine named as missing.",
)
def case_printer_other_laptop(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "The printer is unavailable on the user's laptop.", target="remote")
    _check_remote_guards(body, failures)
    missing = " ".join((body.get("assessment") or {}).get("missing_evidence", [])).lower()
    _check("machine" in missing or "computer" in missing, failures, "missing evidence must name the machine gap")
    failures.extend(_check_citations(body))
    return (not failures, failures, "remote printer case")


@unknown_case(
    "vpn-intermittent", "unfamiliar",
    "VPN drops every 10 minutes: relevant network tools, no duplicates, cited hypotheses.",
)
def case_vpn_intermittent(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "My VPN disconnects every 10 minutes.")
    used = _tools_used(body)
    _check(bool({"get_network_adapters", "get_ip_config", "get_dns_config"} & used), failures, "no network tools used")
    seen: set[str] = set()
    dupes = 0
    for item in body.get("evidence", []):
        if item.get("refresh_of") or not item.get("tool_name"):
            continue
        sig = f"{item['tool_name']}:{item.get('tool_args')}"
        if sig in seen:
            dupes += 1
        seen.add(sig)
    _check(dupes == 0, failures, f"{dupes} duplicate tool calls")
    _check(body.get("tool_calls_used", 99) <= 8, failures, "initial budget exceeded")
    failures.extend(_check_citations(body))
    return (not failures, failures, f"tools={sorted(used)}")


@unknown_case(
    "laptop-slow", "unfamiliar",
    "Sudden slowness: bounded triage with explicit uncertainty, no invented cause.",
)
def case_laptop_slow(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "The laptop suddenly became very slow this morning.")
    _check(bool((body.get("assessment") or {}).get("uncertainties")), failures, "uncertainty not communicated")
    _check(body.get("tool_calls_used", 99) <= 8, failures, "initial budget exceeded")
    _check(bool(body.get("plan", {}).get("steps")), failures, "no plan steps")
    failures.extend(_check_citations(body))
    return (not failures, failures, f"calls={body.get('tool_calls_used')}")


@unknown_case(
    "app-freezes", "unfamiliar",
    "App opens then freezes: investigation completes without any verified claim.",
)
def case_app_freezes(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "The app opens but freezes after about a minute.")
    blob = str(body.get("plans")) + str(body.get("proposals"))
    _check("VERIFIED_RESOLVED" not in blob, failures, "no verified claim may appear unmeasured")
    _check(bool(body.get("questions")) or bool(body.get("plan", {}).get("steps")), failures, "no next direction")
    failures.extend(_check_citations(body))
    return (not failures, failures, "freeze case honest")


@unknown_case(
    "unknown-dialog-screenshot", "unfamiliar",
    "Vague report plus screenshot: metadata-only, consent-honest, question-first.",
)
def case_unknown_dialog_screenshot(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    response = client.post(
        "/api/investigations",
        data={"problem": "A strange dialog keeps appearing.", "share_consent": "true"},
        files={"screenshot": ("dialog.png", png, "image/png")},
    )
    _check(response.status_code == 200, failures, f"screenshot intake failed: {response.status_code}")
    body = response.json()
    shots = [i for i in body.get("evidence", []) if i.get("category") == "screenshot"]
    _check(len(shots) == 1, failures, "screenshot evidence missing")
    _check("base64" not in str(shots[0].get("data", {})), failures, "image bytes leaked into evidence")
    _check(any("consent" in w.lower() for w in body.get("warnings", [])), failures, "consent not acknowledged")
    _check(bool(body.get("questions")), failures, "vague case must ask questions")
    failures.extend(_check_citations(body))
    return (not failures, failures, "screenshot intake honest")


@unknown_case(
    "needs-clarifying-question", "unfamiliar",
    "'Something is broken' with unknown target: the affected machine is asked first.",
)
def case_needs_clarifying_question(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "Something is broken.", target="unknown")
    questions = body.get("questions", [])
    _check(bool(questions), failures, "no clarifying question asked")
    _check("affected computer" in questions[0].get("question", ""), failures, "first question must establish the target")
    _check(body.get("stage") == "CLARIFYING", failures, f"expected CLARIFYING, got {body.get('stage')}")
    failures.extend(_check_citations(body))
    return (not failures, failures, f"q0={questions[0].get('question', '')[:60] if questions else '-'}")


@unknown_case(
    "no-tool-applies", "unfamiliar",
    "Coffee machine leaks: out-of-domain report gets minimal tools and manual guidance.",
)
def case_no_tool_applies(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "The office coffee machine leaks water onto the counter.")
    _check(body.get("tool_calls_used", 99) <= 3, failures, "out-of-domain sweep must stay minimal")
    kinds = {s.get("kind") for s in body.get("plan", {}).get("steps", [])}
    _check(bool(kinds & {"TECHNICIAN_CHECK", "CLARIFYING_QUESTION"}), failures, "no manual guidance offered")
    _check(
        all(c.get("likelihood") in ("medium", "low") for c in (body.get("assessment") or {}).get("causes", [])),
        failures, "must not claim high likelihood without evidence",
    )
    _check(not body.get("proposals"), failures, "no correction may be proposed")
    failures.extend(_check_citations(body))
    return (not failures, failures, f"calls={body.get('tool_calls_used')} kinds={sorted(kinds)}")


@unknown_case(
    "hypothesis-revision", "unfamiliar",
    "Contradicting observation plus technician judgment retires a hypothesis with history.",
)
def case_hypothesis_revision(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(client, "The demo worker is down.")
    inv_id = body["investigation_id"]
    hyp_id = body["hypotheses"][0]["hypothesis_id"]
    body = _turn(client, inv_id, "On site now: the worker process is running fine.", kind="observation")
    response = client.post(
        f"/api/investigations/{inv_id}/hypotheses/{hyp_id}/status",
        json={"status": "ruled_out", "reason": "Worker observed healthy on site."},
    )
    _check(response.status_code == 200, failures, "judgment endpoint failed")
    body = response.json()
    hyp = next(h for h in body["hypotheses"] if h["hypothesis_id"] == hyp_id)
    _check(hyp["status"] == "ruled_out", failures, "hypothesis not retired")
    _check(len(hyp["history"]) >= 2, failures, "history not preserved")
    body = _turn(client, inv_id, "User still reports slowness elsewhere.", kind="observation")
    hyp2 = next(h for h in body["hypotheses"] if h["hypothesis_id"] == hyp_id)
    _check(hyp2["status"] == "ruled_out", failures, "technician judgment was overridden")
    failures.extend(_check_citations(body))
    return (not failures, failures, "revision locked")


@unknown_case(
    "cannot-perform-test", "unfamiliar",
    "Every step impossible: the investigation blocks honestly with reasons kept.",
)
def case_cannot_perform_test(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    body = _investigate(
        client, "Excel won't open this file from Teams. It started happening this morning.",
        target="remote",
    )
    inv_id = body["investigation_id"]
    for _ in range(10):
        open_steps = [s for s in body["plan"]["steps"] if s["status"] in ("suggested", "current")]
        if not open_steps:
            break
        response = client.post(
            f"/api/investigations/{inv_id}/plan/steps/{open_steps[0]['step_id']}/impossible",
            json={"reason": "No access to that machine."},
        )
        if response.status_code != 200:
            failures.append(f"impossible endpoint failed: {response.status_code}")
            break
        body = response.json()
    _check(body.get("stage") == "BLOCKED", failures, f"expected BLOCKED, got {body.get('stage')}")
    _check(bool(body.get("blocked_reason")), failures, "blocked reason missing")
    blocked = [s for s in body["plan"]["steps"] if s["status"] == "blocked"]
    _check(bool(blocked) and all(s.get("outcome") for s in blocked), failures, "blocked outcomes not kept")
    failures.extend(_check_citations(body))
    return (not failures, failures, f"blocked={len(blocked)}")


@unknown_case(
    "verified-recovery-not-assumed", "unfamiliar",
    "A manual 'I fixed it' claim is measured and honestly graded NOT_RESOLVED.",
)
def case_verified_recovery_not_assumed(client: Any) -> tuple[bool, list[str], str]:
    failures: list[str] = []
    previous = os.environ.get("FIELDROOK_FIXTURE_WORKER")
    os.environ["FIELDROOK_FIXTURE_WORKER"] = "failing"
    try:
        body = _investigate(client, "The demo worker is down.")
        inv_id = body["investigation_id"]
        ev_ids = [i["id"] for i in body.get("evidence", []) if i.get("tool_name") == "get_demo_worker_health"]
        created = client.post(
            f"/api/investigations/{inv_id}/plans",
            json={
                "evidence_ids": ev_ids,
                "intended_state": "Demo worker reports healthy.",
                "criteria": [
                    {
                        "description": "Worker health reads healthy.",
                        "tool_name": "get_demo_worker_health",
                        "tool_args": {},
                        "path": "status",
                        "op": "eq",
                        "expected": "healthy",
                    }
                ],
                "guidance": "Restart the worker by hand.",
                "risks": "None in fixture.",
                "remediation_kind": "manual",
            },
        )
        _check(created.status_code == 200, failures, f"plan creation failed: {created.status_code}")
        plan_id = created.json()["plans"][-1]["plan_id"]
        _check(client.post(f"/api/plans/{plan_id}/baseline").status_code == 200, failures, "baseline failed")
        manual = client.post(
            f"/api/plans/{plan_id}/interventions/manual", json={"description": "Restarted by hand."}
        )
        _check(manual.status_code == 200, failures, "manual record failed")
        verified = client.post(f"/api/plans/{plan_id}/verify")
        _check(verified.status_code == 200, failures, f"verify failed: {verified.status_code}")
        plan = next(p for p in verified.json()["plans"] if p["plan_id"] == plan_id)
        _check(plan["verifications"], failures, "no verification recorded")
        _check(
            plan["verifications"][-1]["outcome"] == "NOT_RESOLVED",
            failures, f"claim alone must not verify, got {plan['verifications'][-1]['outcome']}",
        )
        kinds = [i.get("kind") for i in plan.get("interventions", [])]
        _check("manual" in kinds, failures, "manual claim not recorded")
    finally:
        if previous is None:
            os.environ.pop("FIELDROOK_FIXTURE_WORKER", None)
        else:
            os.environ["FIELDROOK_FIXTURE_WORKER"] = previous
    failures.extend(_check_citations(body))
    return (not failures, failures, "manual claim measured honestly")
