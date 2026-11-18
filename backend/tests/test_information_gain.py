"""M033-C: safe, bounded, provenance-aware question selection."""

from __future__ import annotations

import pytest

from app.analysis.information_gain import (
    choose_question,
    review_task_question,
    score_question,
)


def _decision(
    primary: str = "Which users are affected?",
    alternative: str = "Does the failure happen for this user in the browser but not the desktop client?",
    **kwargs,
):
    return choose_question(
        primary, "Identify the affected users.",
        alternative, "Compare the affected user's browser and desktop paths to separate account from client behavior.",
        hypotheses=["User access restriction", "Desktop client problem"],
        **kwargs,
    )


def test_prefers_genuinely_discriminating_safe_alternative():
    result = _decision()
    assert result.selected == "alternative"
    assert result.alternative is not None
    assert result.alternative.score >= result.primary.score + 2
    assert "heuristic" not in result.explanation.lower() or result.selected == "alternative"


def test_original_kept_when_no_alternative():
    result = _decision(alternative="")
    assert result.selected == "primary"
    assert result.alternative is None


def test_tie_preserves_original_and_does_not_add_calls():
    phrase = "Does it fail only on another user profile or on both user profiles?"
    result = choose_question(
        phrase, "Compare user versus machine scope.",
        phrase, "Compare user versus machine scope.",
    )
    assert result.selected == "primary"


def test_near_asked_question_is_penalized():
    before = _decision(asked=["Which users are affected?"])
    after = _decision()
    assert before.primary.score < after.primary.score
    assert before.selected == "alternative"


def test_short_distinct_questions_not_false_duplicates():
    a = score_question(
        "Which users can access the same file?",
        "Compare accounts.",
        asked=["Which users are affected by Teams?"],
    )
    assert "duplicates-prior-question" not in a.signals


@pytest.mark.parametrize(
    "unsafe",
    [
        "Can you disable Windows Defender to see if it fixes the problem?",
        "Can you bypass the firewall security controls for this test?",
        "Can you edit the registry keys to restore access?",
        "Can you restart the computer to test the application?",
        "Can you run this test as administrator?",
    ],
)
def test_proposed_unsafe_or_privileged_alternative_is_ineligible(unsafe):
    result = _decision(
        primary="Can another user open the file in the browser?",
        alternative=unsafe,
    )
    assert result.selected == "primary"
    assert result.alternative is not None
    assert not result.alternative.eligible


def test_unsafe_primary_does_not_block_safe_alternative():
    result = _decision(
        primary="Can you disable the firewall to check the network?",
        alternative="Does it fail on the same network for both users?",
    )
    assert result.selected == "alternative"
    assert result.primary.eligible is False


def test_both_unsafe_questions_withheld_without_generation():
    result = _decision(
        primary="Can you bypass the security controls?",
        alternative="Can you turn off Windows Defender?",
    )
    assert result.selected is None


def test_provided_error_code_should_not_be_requested_again():
    q = "What is the exact error code shown in the Windows application?"
    known = score_question(q, "The code helps identify the fault.", problem="Outlook fails with 0x80070005.")
    unknown = score_question(q, "The code helps identify the fault.", problem="Outlook fails.")
    assert known.score < unknown.score
    assert "asks-known-error-code" in known.signals


def test_generic_more_details_request_scores_poorly():
    vague = score_question("Can you provide more details about the problem?", "More context.", hypotheses=[])
    contrast = score_question(
        "Does the error occur only in the desktop app or also in a browser?",
        "The answer distinguishes local client from account or service causes.",
        hypotheses=["Client issue", "Service issue"],
    )
    assert contrast.score > vague.score
    assert "vague-question" in vague.signals


def test_invalid_question_type_is_rejected():
    assert not score_question("Maybe it is permissions", "Unknown.").eligible
    assert not score_question("", "").eligible


def test_no_unsafe_question_reaches_normalized_triage():
    raw = {
        "question": "Can you disable Windows Defender?",
        "why": "It might prove a cause.",
        "alternative_question": "",
        "alternative_why": "",
        "hypotheses": [],
        "next_check": "Read the Windows event log.",
    }
    updated, review = review_task_question(
        "triage", raw, problem="An application crashes.", hypotheses=[],
        asked=[], target="remote",
    )
    assert review is not None and review.selected is None
    assert updated is not None and updated["question"] == ""
    assert updated["next_check"] == "Read the Windows event log."
    assert raw["question"] == "Can you disable Windows Defender?"


def test_triage_alternative_swaps_question_and_why_without_mutation():
    raw = {
        "question": "Which users are affected?",
        "why": "Check scope.",
        "alternative_question": "Does the problem happen in a browser but not the desktop client?",
        "alternative_why": "This distinguishes the desktop client from an account or service problem.",
        "hypotheses": [{"title": "Desktop client problem"}, {"title": "Account restriction"}],
    }
    updated, review = review_task_question(
        "triage", raw, problem="Service fails on another computer.",
        hypotheses=["Desktop client problem", "Account restriction"], asked=[],
        target="remote",
    )
    assert review is not None and review.selected == "alternative"
    assert updated is not None
    assert updated["question"] == raw["alternative_question"]
    assert updated["why"] == raw["alternative_why"]
    assert raw["question"] == "Which users are affected?"


def test_reassess_nonquestion_technician_check_is_not_converted():
    raw = {
        "next_step": "Inspect the application event log around the failure time.",
        "alternative_question": "Does the error occur in browser as well as desktop?",
        "verdict": "No new evidence yet.",
    }
    updated, review = review_task_question(
        "reassess", raw, problem="App won't launch.", hypotheses=[],
        asked=[], target="remote",
    )
    assert review is None
    assert updated == raw


def test_reassess_question_can_be_replaced():
    raw = {
        "next_step": "Which users are affected?",
        "verdict": "Need more data.",
        "alternative_question": "Can the affected user launch the app in a new profile but not the original profile?",
        "alternative_why": "Contrasts profile-local corruption with machine-wide failure.",
    }
    updated, review = review_task_question(
        "reassess", raw, problem="The app crashes.",
        hypotheses=["Profile corruption", "Machine-wide failure"], asked=[],
        target="remote",
    )
    assert review is not None and review.selected == "alternative"
    assert updated is not None and updated["next_step"] == raw["alternative_question"]


@pytest.mark.parametrize("task", ["plan", "synthesize", "vision"])
def test_other_tasks_never_reranked(task):
    raw = {"question": "Can you disable the firewall?"}
    updated, review = review_task_question(
        task, raw, problem="x", hypotheses=[], asked=[], target="remote",
    )
    assert updated is raw and review is None


def test_none_task_payload_stays_none():
    updated, review = review_task_question(
        "triage", None, problem="x", hypotheses=[], asked=[], target="remote",
    )
    assert updated is None and review is None


def test_score_is_bounded_and_no_diagnosis_claimed():
    item = score_question(
        "Does the problem happen on another computer but not this one?",
        "The comparison distinguishes a device cause from a service-wide cause.",
        hypotheses=["Device problem", "Service-wide outage"],
    )
    assert 0 <= item.score <= 10
    assert not any("proven" in s for s in item.signals)


def test_known_onset_is_not_reasked() -> None:
    q = "When did the application errors start occurring?"
    known = score_question(q, "The timing may matter.", problem="The errors began this morning.")
    unknown = score_question(q, "The timing may matter.", problem="The application fails.")
    assert "asks-known-onset" in known.signals
    assert known.score < unknown.score


def test_high_gain_technician_check_can_beat_low_gain_question() -> None:
    from app.analysis.information_gain import score_technician_check

    raw = {
        "question": "Which users are affected?",
        "why": "Check broad scope.",
        "hypotheses": [{"title": "User profile issue"}, {"title": "Application add-in issue"}],
        "next_check": "Try launching the same application in safe mode to compare startup behavior.",
    }
    improved, decision = review_task_question(
        "triage", raw, problem="App will not launch.",
        hypotheses=["User profile issue", "Application add-in issue"],
        asked=[], target="remote",
    )
    assert decision is not None
    assert decision.check is not None and decision.check.eligible
    assert score_technician_check(raw["next_check"]).score >= 5
    assert decision.selected == "check"
    assert improved is not None
    assert improved["question"] == ""
    assert improved["next_check"] == raw["next_check"]
    assert raw["question"] == "Which users are affected?"


def test_unsafe_model_check_is_not_promoted_as_read_only() -> None:
    raw = {
        "question": "Can the same user log in through the browser?",
        "why": "The alternative path can distinguish the client.",
        "next_check": "Disable Windows Defender and retry.",
    }
    updated, decision = review_task_question(
        "triage", raw, problem="Application cannot start.",
        hypotheses=["Client issue"], asked=[], target="remote",
    )
    assert updated is not None and updated["next_check"] == ""
    assert decision is not None and decision.check is not None
    assert decision.check.eligible is False
    assert raw["next_check"] == "Disable Windows Defender and retry."


def test_weak_check_does_not_displace_stronger_question():
    raw = {
        "question": "Does the affected user's desktop fail while browser access works?",
        "why": "The different outcomes would distinguish client and account problems.",
        "next_check": "Check general update status.",
        "hypotheses": [{"title": "Client issue"}, {"title": "Account issue"}],
    }
    updated, decision = review_task_question(
        "triage", raw, problem="App fails.", hypotheses=["Client issue", "Account issue"],
        asked=[], target="remote",
    )
    assert decision is not None and decision.selected == "primary"
    assert updated is not None and updated["question"] == raw["question"]


def test_reported_hex_error_code_cannot_be_silently_changed():
    report = "Outlook will not start; error 0x80070005 is shown."
    original = score_question(
        "Can the user reproduce the same 0x80070005 error in safe mode?",
        "Compare a controlled launch condition.", problem=report,
    )
    invented = score_question(
        "Does the same 0x80070105 error appear on the other machine?",
        "Compare device scope.", problem=report,
    )
    assert original.eligible
    assert not invented.eligible
    assert "conflicting-reported-error-code" in invented.signals


def test_reported_hex_code_check_withheld_and_safe_question_retained():
    original = {
        "question": "Can the user open the same app with a different profile?",
        "why": "Compare account versus machine cause.",
        "next_check": "Check event log for error 0x80070105.",
    }
    filtered, review = review_task_question(
        "triage", original,
        problem="The user reported 0x80070005.",
        hypotheses=["User profile", "Machine-wide failure"],
        asked=[], target="remote",
    )
    assert filtered is not None
    assert filtered["next_check"] == ""
    assert filtered["question"] == original["question"]
    assert review is not None and review.check is not None
    assert "conflicting-reported-error-code" in review.check.signals


def test_unrecognized_but_not_classified_unsafe_check_not_discarded():
    raw = {
        "question": "Which users are affected?",
        "why": "Find scope.",
        "next_check": "Run ipconfig /all for network configuration details.",
    }
    filtered, review = review_task_question(
        "triage", raw, problem="Network issue", hypotheses=[], asked=[], target="remote",
    )
    assert filtered is not None
    assert filtered["next_check"] == raw["next_check"], "Unknown heuristic is not proof of danger"
    assert review is not None and review.check is not None
    assert "not-a-check" in review.check.signals


def test_vague_failure_boundary_question_is_not_mistaken_for_high_gain():
    unclear = score_question(
        "At what point does the VPN disconnection stop working?",
        "The answer changes the diagnosis.",
        problem="The VPN disconnects frequently.",
    )
    controlled = score_question(
        "Does the underlying network stay connected while the VPN drops?",
        "Compare VPN client failure with underlying connectivity failure.",
        problem="The VPN disconnects frequently.",
    )
    assert "ambiguous-failure-boundary" in unclear.signals
    assert controlled.score > unclear.score
