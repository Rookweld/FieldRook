"""M033-G — model decision source links must never become proof by existence."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.analysis.assist import mark_hypothesis
from app.analysis.hypothesis_decisions import (
    review_hypothesis_changes,
    technician_report_refs,
)
from app.investigations.store import InvestigationState
from app.schemas import Hypothesis, HypothesisEvent


def state(target="local"):
    state = InvestigationState(
        id="inv-source-test", problem="An application fails.",
        service_name=None, has_image=False, target=target,
        messages=[
            {"role": "system", "content": "Some instructions."},
            {"role": "user", "content": "The application fails after the driver changed."},
            {"role": "assistant", "content": "What did you observe?"},
            {"role": "user", "content": "Technician observation: It fails in normal mode."},
        ],
        hypotheses=[
            Hypothesis(
                hypothesis_id="h-driver", title="Network adapter driver conflict",
                history=[HypothesisEvent(round=0,status="active",reason="Recorded.")],
            ),
        ],
    )
    state.add_evidence(
        "os_info", "tool:get_os_info:live", {"os": "Windows"},
        tool_name="get_os_info",
    )
    state.add_evidence(
        "report", "report:technician", {"claim": "Driver updated"},
    )
    state.add_evidence(
        "service", "tool:get_service:live", {},
        error="Timeout", tool_name="get_service",
    )
    state.add_evidence(
        "os_info", "fixture:os_info", {"os": "Windows fixture"},
        tool_name="get_os_info",
    )
    return state


def proposed(**link):
    return {
        "verdict": "The driver seems less likely.",
        "weakened": ["Network adapter driver conflict"],
        "next_step": "Review the relevant event history.",
        "decision_links": [{
            "hypothesis": "Network adapter driver conflict",
            **link,
        }],
    }


def inspect(s, raw=None, mode="observe"):
    return review_hypothesis_changes(
        raw if raw is not None else proposed(),
        hypotheses=s.hypotheses, evidence=s.evidence, messages=s.messages,
        round_no=2, start_index=len(s.hypothesis_decisions),
        mode=mode, target=s.target,
    )


def test_report_refs_are_stable_message_indices_not_evidence():
    s=state()
    assert technician_report_refs(s.messages)==["report:1","report:3"]
    assert technician_report_refs([{"role":"user","content":[{"type":"image_url"}]}])==[]


def test_valid_host_and_report_links_still_not_claimed_as_proof():
    s=state()
    raw=proposed(
        evidence_ids=["ev-1"],report_refs=["report:3"],
        why="Technician's report and an OS reading suggest rechecking.",
    )
    result, decisions=inspect(s,raw)
    assert result is raw, "Observe must never mutate provider output"
    assert len(decisions)==1
    row=decisions[0]
    assert row.link_status=="mixed"
    assert row.evidence_ids==["ev-1"]
    assert row.measured_evidence_ids==["ev-1"]
    assert row.report_refs==["report:3"]
    assert row.review_state=="observed"
    assert "unverified" in row.provenance_note
    assert "ev-1" not in row.report_refs


def test_invalid_and_failed_citations_are_rejected():
    s=state()
    _, rows=inspect(s,proposed(
        evidence_ids=["ev-999","ev-3"],report_refs=["report:99"],
        why="All evidence ids are trusted (not true).",
    ))
    assert rows[0].link_status=="invalid"
    assert rows[0].evidence_ids==[]
    assert set(rows[0].rejected_refs)=={
        "unknown-evidence-ref","failed-or-empty-collection-ref","unknown-report-ref"
    }


def test_fixture_not_mislabeled_as_live_host_measurement():
    s=state()
    _, rows=inspect(s,proposed(evidence_ids=["ev-4"]))
    assert rows[0].evidence_ids==["ev-4"]
    assert rows[0].measured_evidence_ids==[]
    assert rows[0].link_status=="evidence_cited"


def test_technician_report_is_valid_but_never_measured():
    s=state()
    _, rows=inspect(s,proposed(report_refs=["report:3"]))
    assert rows[0].link_status=="report_only"
    assert rows[0].measured_evidence_ids==[]


def test_remote_target_cannot_cite_local_host_tool_as_remote_measurement():
    s=state(target="remote")
    _,rows=inspect(s,proposed(evidence_ids=["ev-1"],report_refs=["report:3"]))
    assert rows[0].link_status=="invalid"
    assert rows[0].evidence_ids==[]
    assert "wrong-host-ref" in rows[0].rejected_refs
    assert rows[0].report_refs==["report:3"]


def test_no_valid_link_is_marked_uncited():
    s=state()
    _,rows=inspect(s,proposed(why="I suspect something."))
    assert rows[0].link_status=="uncited"
    assert "No valid" in rows[0].provenance_note


def test_require_review_is_explicit_gate_and_preserves_raw():
    s=state()
    raw=proposed(evidence_ids=["ev-1"],why="Inspect a measurement.")
    untouched=deepcopy(raw)
    result, rows=inspect(s,raw,mode="require_review")
    assert raw==untouched
    assert result is not raw
    assert result["weakened"]==[]
    assert result["next_step"]==raw["next_step"]
    assert rows[0].review_state=="pending_technician"
    assert rows[0].proposed_status=="weakened"


def test_off_mode_creates_no_journal_and_changes_nothing():
    s=state()
    raw=proposed(evidence_ids=["ev-1"])
    after, rows=inspect(s,raw,mode="off")
    assert after is raw and rows==[]


def test_unknown_hypothesis_is_never_promoted_to_a_journal_entry():
    s=state()
    raw={"weakened":["Imaginary hypothesis"],"next_step":"Check again."}
    _,rows=inspect(s,raw)
    assert rows==[]
    gated,rows=inspect(s,raw,mode="require_review")
    assert rows==[] and gated["weakened"]==[]


def test_duplicate_titles_generate_only_one_record():
    s=state()
    raw={"weakened":[s.hypotheses[0].title,s.hypotheses[0].title.upper()],
         "decision_links":"untrusted"}
    _,rows=inspect(s,raw)
    assert len(rows)==1


def test_malformed_model_objects_do_not_crash():
    s=state()
    for raw in (
        {"weakened":"Network adapter driver conflict"},
        {"weakened":[None,42,{}], "decision_links":[None]},
        {"weakened":[s.hypotheses[0].title], "decision_links":[{
            "hypothesis":s.hypotheses[0].title,
            "evidence_ids":[None,{}, "x"*100], "report_refs":[False, "x"*100],
            "why":42,
        }]},
    ):
        after, rows=inspect(s,raw,mode="require_review")
        assert after["weakened"]==[]


def test_existing_technician_judgment_marks_only_latest_pending_proposal():
    s=state()
    for i in range(2):
        _,rows=inspect(s,mode="require_review")
        s.hypothesis_decisions.extend(rows)
    assert len(s.hypothesis_decisions)==2
    changed=mark_hypothesis(
        s,"h-driver","weakened","Technician judgment: compared the event logs.",2,
    )
    assert changed
    assert s.hypothesis_decisions[-1].review_state=="technician_applied"
    assert s.hypothesis_decisions[0].review_state=="pending_technician"
    assert any(a.title=="Hypothesis decision reviewed" for a in s.activity)


def test_explicit_technician_override_is_recorded():
    s=state()
    _,rows=inspect(s,mode="require_review")
    s.hypothesis_decisions.extend(rows)
    changed=mark_hypothesis(
        s,"h-driver","ruled_out","Technician judgment: confirmed alternate cause.",2,
    )
    assert changed
    assert rows[0].review_state=="technician_overrode"


def test_non_technician_change_cannot_mark_proposal_as_approved():
    s=state()
    _,rows=inspect(s,mode="require_review")
    s.hypothesis_decisions.extend(rows)
    assert mark_hypothesis(s,"h-driver","weakened","Model reassessment.",2)
    assert rows[0].review_state=="pending_technician"


def test_state_response_contains_structured_decision_log():
    s=state()
    _,rows=inspect(s,mode="require_review")
    s.hypothesis_decisions.extend(rows)
    response=s.to_response(uses_fixtures=False)
    assert response.hypothesis_decisions[0].decision_id=="decision-1"
    assert response.model_dump(mode="json")["hypothesis_decisions"][0]["link_status"]=="uncited"


def test_sqlite_roundtrip_preserves_decisions_and_older_rows(monkeypatch,tmp_path):
    from app.investigations import persistence
    monkeypatch.setenv("FIELDROOK_DB_PATH",str(tmp_path/"decision_test.sqlite"))
    s=state()
    _,rows=inspect(s,proposed(report_refs=["report:3"]),mode="require_review")
    s.hypothesis_decisions.extend(rows)
    persistence.save_state(s)
    saved=persistence.load_state(s.id)
    assert saved is not None
    assert saved.hypothesis_decisions[0].report_refs==["report:3"]
    assert saved.hypothesis_decisions[0].review_state=="pending_technician"
    assert saved.to_response(uses_fixtures=False).hypothesis_decisions[0].hypothesis_id=="h-driver"


def test_evidence_ref_invalid_when_same_id_reused_from_wrong_source():
    s=state(target="remote")
    _,rows=inspect(s,proposed(evidence_ids=["ev-1","ev-2"]))
    assert rows[0].evidence_ids==["ev-2"]
    assert rows[0].link_status=="invalid"
    assert "wrong-host-ref" in rows[0].rejected_refs


def test_superseded_measurements_remain_history_not_current_proof():
    s=state()
    s.add_evidence(
        "os_info", "tool:get_os_info:live", {"os": "Windows 11"},
        tool_name="get_os_info", refresh_of="ev-1",
    )
    _,rows=inspect(s,proposed(evidence_ids=["ev-1","ev-5"]))
    assert rows[0].evidence_ids==["ev-5"]
    assert "superseded-evidence-ref" in rows[0].rejected_refs
    assert rows[0].link_status=="invalid"


def test_empty_tool_reading_is_not_accepted_as_succesful_measurement():
    s=state()
    s.add_evidence("os_info","tool:get_os_info:live",{},tool_name="get_os_info")
    _,rows=inspect(s,proposed(evidence_ids=["ev-5"]))
    assert rows[0].evidence_ids==[]
    assert "failed-or-empty-collection-ref" in rows[0].rejected_refs


def test_tool_source_marked_fixture_must_never_be_counted_as_live_measurement():
    s=state()
    s.add_evidence(
        "os_info","tool:get_os_info:fixture",
        {"os":"Fixture operating system"},
        tool_name="get_os_info",
    )
    _,rows=inspect(s,proposed(evidence_ids=["ev-5"]))
    assert rows[0].evidence_ids==["ev-5"]
    assert rows[0].measured_evidence_ids==[]


def test_same_status_technician_acceptance_is_a_review_not_a_404():
    s = state()
    s.hypotheses[0].status = "weakened"
    _, rows = inspect(s, mode="require_review")
    s.hypothesis_decisions.extend(rows)
    original_events = len(s.hypotheses[0].history)

    assert mark_hypothesis(
        s, "h-driver", "weakened",
        "Technician judgment: I independently verified the driver conflict is less likely.", 3,
    )
    assert rows[0].review_state == "technician_applied"
    assert len(s.hypotheses[0].history) == original_events + 1
    assert s.hypotheses[0].history[-1].reason.startswith("Technician judgment")
    assert not mark_hypothesis(
        s, "h-driver", "weakened", "Technician judgment: duplicate submission.", 4,
    )


def test_same_status_technician_override_can_preserve_active_hypothesis():
    s = state()  # Starts active; the model requests weakened.
    _, rows = inspect(s, mode="require_review")
    s.hypothesis_decisions.extend(rows)
    assert mark_hypothesis(
        s, "h-driver", "active",
        "Technician judgment: the collected source does not support weakening.", 3,
    )
    assert rows[0].review_state == "technician_overrode"
    assert s.hypotheses[0].status == "active"
    assert s.hypotheses[0].history[-1].reason.startswith("Technician judgment")


def test_status_api_records_same_status_override_and_persists(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.investigations.store import store

    monkeypatch.setenv("FIELDROOK_DB_PATH", str(tmp_path / "manual_review_api.sqlite"))
    monkeypatch.setenv("FIELDROOK_FIXTURES", "always")
    s = state()
    _, rows = inspect(s, mode="require_review")
    s.hypothesis_decisions.extend(rows)
    store.save(s)

    response = TestClient(app).post(
        f"/api/investigations/{s.id}/hypotheses/h-driver/status",
        json={"status": "active", "reason": "This is only a report; keep the cause open."},
    )
    assert response.status_code == 200, response.text
    decision = response.json()["hypothesis_decisions"][0]
    assert decision["review_state"] == "technician_overrode"
    again = store.get(s.id)
    assert again is not None
    assert again.hypothesis_decisions[0].review_state == "technician_overrode"
    assert again.hypotheses[0].history[-1].reason.startswith("Technician judgment")


def test_model_reason_redacts_secrets_before_persistence():
    s = state()
    _, rows = inspect(s, proposed(
        report_refs=["report:3"],
        why="User alice@example.com reported password=hunter2 on DOMAIN\\alice.",
    ))
    reason = rows[0].reason
    assert "alice@example.com" not in reason
    assert "hunter2" not in reason
    assert "[email redacted]" in reason
    assert "[secret redacted]" in reason
