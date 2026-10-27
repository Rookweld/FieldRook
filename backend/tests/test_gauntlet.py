"""Gauntlet fixture cases as CI regression tests (deterministic, no key)."""

import os

import pytest

os.environ["MODEL_API_KEY"] = ""

from eval.cases import CASES, TOOL_CASES  # noqa: E402
from eval.run import _banned_claim, run_case, run_tool_case  # noqa: E402


def test_banned_claim_allows_hedged_proven() -> None:
    assert _banned_claim("the cause is proven", "proven") is True
    assert _banned_claim("causation is not proven", "proven") is False
    assert _banned_claim("the distinction is unproven", "proven") is False
    assert _banned_claim("nothing proven yet", "proven") is False
    assert _banned_claim("definitely the driver", "definitely") is True


@pytest.mark.parametrize("case", [c for c in CASES if not c.live_model], ids=lambda c: c.id)
def test_gauntlet_fixture_case(case) -> None:  # type: ignore[no-untyped-def]
    result = run_case(case)
    assert result["passed"], f"{case.id}: {result['failures']} (ref: {case.reference})"


@pytest.mark.parametrize("case", TOOL_CASES, ids=lambda c: c.id)
def test_gauntlet_tool_case(case) -> None:  # type: ignore[no-untyped-def]
    result = run_tool_case(case)
    assert result["passed"], f"{case.id}: {result['failures']}"
