"""Audit helpers: every action-lifecycle event becomes a timeline record."""

from __future__ import annotations

from typing import Any


def record_execution_started(state: Any, proposal: Any) -> None:
    state.add_activity(
        "executed",
        f"Executing: {proposal.action_id} on {proposal.target}",
        "Approved execution started.",
    )


def record_execution_finished(
    state: Any, proposal: Any, outcome: str, detail: str, evidence_ids: list[str]
) -> None:
    state.add_activity("verified", f"{proposal.action_id}: {outcome}", detail, evidence_ids=evidence_ids)


def record_verification_started(state: Any, proposal: Any) -> None:
    state.add_activity(
        "verification_started",
        f"Verifying: {proposal.action_id} on {proposal.target}",
        "Independent post-action diagnostics running.",
    )
