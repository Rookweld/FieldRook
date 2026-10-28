"""M019 guidance safety filter: impact classification and unsafe flagging."""

import json

from app.analysis.assist import merge_plan
from app.analysis.guidance import GuidanceVerdict, classify_guidance, scan_texts_for_unsafe
from app.analysis.validate import validate_assessment_output
from app.investigations.store import InvestigationState
from app.schemas import SuggestedPlan, SuggestedPlanStep


def _classify(text: str, **kwargs) -> GuidanceVerdict:
    return classify_guidance(text, **kwargs)


def test_registered_automation_is_read_only() -> None:
    verdict = _classify("Re-check ev-1 with get_os_info.", kind="AUTOMATED_READ_ONLY", tool_registered=True)
    assert verdict.impact == "READ_ONLY"
    assert verdict.safety_note == ""


def test_technician_inspection_is_manual_information() -> None:
    verdict = _classify("Check Event Viewer for crash entries around the failure time.")
    assert verdict.impact == "MANUAL_INFORMATION"
    assert verdict.safety_note == ""


def test_service_restart_is_system_change() -> None:
    verdict = _classify("Restart the Print Spooler service and test printing.")
    assert verdict.impact == "SYSTEM_CHANGE"
    assert "service" in verdict.safety_note


def test_elevated_repair_is_privileged() -> None:
    verdict = _classify("Run sfc /scannow in an elevated Command Prompt.")
    assert verdict.impact == "PRIVILEGED_ACTION"
    assert "elevat" in verdict.safety_note


def test_chkdsk_repair_is_disruptive() -> None:
    verdict = _classify("Run chkdsk /f on C: and reboot.")
    assert verdict.impact == "POTENTIALLY_DISRUPTIVE"
    assert "chkdsk" in verdict.safety_note


def test_bare_chkdsk_stays_manual_information() -> None:
    verdict = _classify("Run chkdsk on C: without flags to read the volume state.")
    assert verdict.impact == "MANUAL_INFORMATION"


def test_admin_bypass_is_unsafe() -> None:
    verdict = _classify("Create a new administrator account to bypass the permission error.")
    assert verdict.impact == "UNSUPPORTED_OR_UNSAFE"
    assert "bypass" in verdict.safety_note


def test_defender_disable_is_unsafe() -> None:
    verdict = _classify("Temporarily disable Windows Defender and retry the install.")
    assert verdict.impact == "UNSUPPORTED_OR_UNSAFE"


def test_unbacked_automation_is_unsupported() -> None:
    verdict = _classify(
        "Capture packets on the affected adapter.",
        kind="AUTOMATED_READ_ONLY",
        tool_registered=False,
    )
    assert verdict.impact == "UNSUPPORTED_OR_UNSAFE"
    assert "No registered FieldRook tool" in verdict.safety_note


def test_negated_advice_is_not_flagged() -> None:
    verdict = _classify("Do not disable the firewall to work around this error.")
    assert verdict.impact == "MANUAL_INFORMATION"
    assert verdict.safety_note == ""


def test_disk_step_on_network_problem_gets_relevance_note() -> None:
    verdict = _classify(
        "Run chkdsk /f on C:.",
        problem="Cannot reach the network share since this morning.",
    )
    assert verdict.impact == "POTENTIALLY_DISRUPTIVE"
    assert "network-related" in verdict.safety_note


def test_host_wording_on_remote_target_gets_relevance_note() -> None:
    verdict = _classify(
        "Open Event Viewer on this computer and report errors.",
        problem="App crashes.",
        target="remote",
    )
    assert verdict.impact == "MANUAL_INFORMATION"
    assert "elsewhere" in verdict.safety_note


def test_free_text_scan_flags_unsafe_actions_but_skips_negation() -> None:
    findings = scan_texts_for_unsafe(
        [
            "Restart the service and retest.",
            "Format D: to clear the corruption.",
            "Do not disable the firewall; investigate instead.",
        ]
    )
    assert len(findings) == 1
    assert "Format D:" in findings[0]


# ---------------------------------------------------------------------------
# Merge + validation wiring
# ---------------------------------------------------------------------------


def _live_state(**overrides) -> InvestigationState:
    params = {
        "id": "inv-test",
        "problem": "Test problem.",
        "service_name": None,
        "has_image": False,
        "messages": [{"role": "user", "content": "Test problem."}],
    }
    params.update(overrides)
    return InvestigationState(**params)


def _assessed(raw_plan) -> object:
    payload = {
        "summary": "Test summary.",
        "facts": [],
        "causes": [],
        "uncertainties": [],
        "missing_evidence": [],
        "next_actions": ["Check the thing."],
        "explanation": "Test explanation.",
        "plan": raw_plan,
    }
    return validate_assessment_output(json.dumps(payload), set(), "m", "live")


def test_merge_demotes_unbacked_automation_and_warns() -> None:
    state = _live_state()
    state.assessment = _assessed(None)
    assert state.assessment is not None
    state.assessment.suggested_plan = SuggestedPlan(
        steps=[
            SuggestedPlanStep(
                instruction="Capture packets on the affected adapter.",
                kind="AUTOMATED_READ_ONLY",
            )
        ]
    )
    merge_plan(state, 1)
    assert state.plan is not None
    step = state.plan.steps[0]
    assert step.kind == "TECHNICIAN_CHECK"
    assert step.tool_name is None
    assert step.guidance_impact == "UNSUPPORTED_OR_UNSAFE"
    assert "No registered FieldRook tool" in step.safety_note
    assert any("Guidance flagged" in w for w in state.warnings)


def test_merge_flags_unsupported_named_tool() -> None:
    state = _live_state()
    state.assessment = _assessed(
        {
            "steps": [
                {
                    "instruction": "Sniff packets with FieldRook.",
                    "kind": "AUTOMATED_READ_ONLY",
                    "tool_name": "packet_sniffer",
                }
            ]
        }
    )
    merge_plan(state, 1)
    assert state.plan is not None
    step = state.plan.steps[0]
    assert step.kind == "TECHNICIAN_CHECK"
    assert step.guidance_impact == "UNSUPPORTED_OR_UNSAFE"
    assert "packet_sniffer" in step.safety_note
    assert any("Guidance flagged" in w for w in state.warnings)


def test_merge_marks_registered_tool_step_read_only() -> None:
    state = _live_state()
    state.assessment = _assessed(
        {
            "steps": [
                {
                    "instruction": "Re-check ev-1 with get_os_info.",
                    "kind": "AUTOMATED_READ_ONLY",
                    "tool_name": "get_os_info",
                }
            ]
        }
    )
    merge_plan(state, 1)
    assert state.plan is not None
    step = state.plan.steps[0]
    assert step.kind == "AUTOMATED_READ_ONLY"
    assert step.tool_name == "get_os_info"
    assert step.guidance_impact == "READ_ONLY"
    assert step.safety_note == ""
    assert not any("Guidance flagged" in w for w in state.warnings)


def test_runbook_steps_classified_and_unsafe_actions_warned() -> None:
    payload = {
        "summary": "Test summary.",
        "facts": [],
        "causes": [],
        "uncertainties": [],
        "missing_evidence": [],
        "next_actions": ["Check the thing.", "Disable the firewall and retry."],
        "next_steps": [{"step": "Run chkdsk /f on C:."}],
        "explanation": "Test explanation.",
    }
    result = validate_assessment_output(json.dumps(payload), set(), "m", "live")
    assert result.next_steps[0].guidance_impact == "POTENTIALLY_DISRUPTIVE"
    assert "chkdsk" in result.next_steps[0].safety_note
    assert any("unsafe guidance" in w for w in result.validation_warnings)
