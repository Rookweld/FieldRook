"""Further M040 regression checks from the real post-patch Qwen3:8B replay."""

from app.analysis.assist import _already_answered_in_reports, _settle_questions
from app.investigations.store import InvestigationState
from app.schemas import ClarifyingQuestion


def state(problem: str = "A VPN connection intermittently drops.") -> InvestigationState:
    return InvestigationState(
        id="m040-followup-test", problem=problem, service_name=None, has_image=False,
        target="remote", messages=[{"role": "user", "content": problem}],
    )


def test_wrapped_duplicate_question_is_suppressed_from_original_report() -> None:
    s = state(
        "A Windows 11 PC runs a custom local diagnostic bridge consisting of "
        "a Windows launcher, a local tunnel-client process, and a Python MCP "
        "server. The launcher briefly indicates ONLINE but switches OFFLINE "
        "within seconds. The launcher stays open."
    )
    question = (
        "Can you provide or check the following: Does the launcher indicate "
        "ONLINE briefly and then switch OFFLINE within seconds when attempting "
        "to launch the Python MCP server?"
    )
    assert _already_answered_in_reports(s, question)


def test_profile_path_question_stays_open_until_profile_can_be_read() -> None:
    s = state()
    question = (
        "Can you verify the exact path where the YAML profile is located "
        "and check if the launcher is configured to use that path?"
    )
    s.messages.append({
        "role": "user",
        "content": (
            "Technician observation: tunnel-client cannot find its YAML "
            "profile in the default directory. The YAML profile exists in "
            "AppData/Roaming but the profile configuration was not changed yet."
        ),
    })
    assert not _already_answered_in_reports(s, question)
    s.messages.append({
        "role": "user",
        "content": (
            "Technician configured tunnel-client to use the existing "
            "profile directory. It now reads its YAML and starts the Python "
            "MCP subprocess."
        ),
    })
    assert _already_answered_in_reports(s, question)


def test_process_execution_question_retires_once_process_starts() -> None:
    s = state()
    question = (
        "Can you check if the launcher script has the correct permissions "
        "and path to execute the tunnel-client process?"
    )
    assert not _already_answered_in_reports(s, question)
    s.messages.append({
        "role": "user",
        "content": (
            "After the PowerShell module was repaired, the tunnel-client "
            "now launches but exits quickly because it cannot locate its "
            "YAML configuration."
        ),
    })
    assert _already_answered_in_reports(s, question)
    s.questions.append(ClarifyingQuestion(
        question_id="q-1", question=question, source="model", asked_round=1,
    ))
    notes = _settle_questions(s, 3, [])
    assert s.questions[0].status == "retired"
    assert "report" in s.questions[0].retired_note
    assert notes


def test_unverified_profile_existence_does_not_hide_startup_check() -> None:
    s = state()
    s.messages.append({
        "role": "user",
        "content": "A profile file exists on disk, but the client still fails on launch.",
    })
    assert not _already_answered_in_reports(
        s, "Can you verify the exact path where the YAML profile is located?"
    )
