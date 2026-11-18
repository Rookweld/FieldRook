"""Frozen M032 scenario contracts: baseline fairness and remote safety."""

from eval.challenge.m032_scenarios import M032_M031_TEAMS, M032_SCENARIOS


def test_fixed_suite_ids_and_remote_scope() -> None:
    assert [s.id for s in M032_SCENARIOS] == [
        "m031-teams-single-user", "outlook-startup", "vpn-intermittent"
    ]
    assert all(s.target == "remote" for s in M032_SCENARIOS)
    assert all(not s.image and not s.collector_package for s in M032_SCENARIOS)
    assert all(len({check.id for check in s.checks}) == len(s.checks) for s in M032_SCENARIOS)


def test_m031_second_user_update_is_fixed_timing() -> None:
    scenario = M032_M031_TEAMS
    assert scenario.max_turns == 2
    beats = [b for b in scenario.beats if b.deliver_at_turn == 1]
    assert len(beats) == 1
    beat = beats[0]
    assert beat.kind == "observation"
    assert "second user" in beat.answer.lower()
    assert "no additional host measurements" in beat.answer.lower()
    assert "0x80070005" in beat.answer
    assert all(check.evaluator != "tools_used_any" for check in scenario.checks)


def test_model_checks_not_embedded_in_synthetic_inputs() -> None:
    scenario = M032_M031_TEAMS
    assert "weaken" not in scenario.opening.lower()
    assert "hypothesis" not in scenario.opening.lower()
    assert "confirmed" not in scenario.opening.lower()
    assert not any(check.description in scenario.opening for check in scenario.checks)


from types import SimpleNamespace

from eval.challenge.simulator import _ev_m032_file_fault_deprioritized


def _snapshot(turn: int, hypotheses: dict[str, tuple[str, str]]) -> object:
    return SimpleNamespace(
        turn=turn,
        hyp_titles={key: title for key, (title, _status) in hypotheses.items()},
        hypotheses={key: status for key, (_title, status) in hypotheses.items()},
    )


def test_same_turn_file_fault_must_be_weakened_not_later() -> None:
    before = _snapshot(0, {"f": ("Corrupted Excel file", "active")})
    after = _snapshot(1, {"f": ("Corrupted Excel file", "active")})
    belated = _snapshot(2, {"f": ("Corrupted Excel file", "weakened")})
    passed, reason = _ev_m032_file_fault_deprioritized(
        [before, after, belated],
        {"b-other-user-succeeds": 1},
        {}, {"beat": "b-other-user-succeeds", "file_fault_terms": ["corrupt"]},
        None,
    )
    assert passed is False
    assert "Still treating" in reason


def test_correct_immediate_update_passes() -> None:
    before = _snapshot(0, {"f": ("File format compatibility issue", "active")})
    after = _snapshot(1, {"f": ("File format compatibility issue", "weakened")})
    passed, _ = _ev_m032_file_fault_deprioritized(
        [before, after],
        {"b-other-user-succeeds": 1},
        {}, {"beat": "b-other-user-succeeds", "file_fault_terms": ["file format"]},
        None,
    )
    assert passed is True


def test_missing_counterexample_does_not_pass() -> None:
    passed, _ = _ev_m032_file_fault_deprioritized(
        [_snapshot(0, {})],
        {}, {},
        {"beat": "b-other-user-succeeds", "file_fault_terms": ["corrupt"]},
        None,
    )
    assert passed is False
