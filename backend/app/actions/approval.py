"""Human approval workflow: short-lived, single-use, exact-match authorization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..schemas import ActionProposal
from .policies import (
    APPROVAL_TTL_S,
    args_hash,
    check_preconditions,
    investigation_digest,
    token_hash,
    validate_proposal,
)
from .registry import ApprovalError, get_action

# Approval is never inferred from chat: only these explicit API operations count.


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_proposal(
    state: Any,
    action_id: object,
    target: object,
    args: object,
    reason: str,
    evidence_ids: list[str],
) -> ActionProposal:
    spec, validated_args = validate_proposal(action_id, target, args)
    assert isinstance(target, str)
    check_preconditions(spec, target)
    known = {item.id for item in state.evidence}
    refs = [eid for eid in evidence_ids if eid in known]
    proposal = ActionProposal(
        proposal_id=f"prop-{uuid4().hex[:12]}",
        investigation_id=state.id,
        action_id=spec.id,
        target=target,
        args=validated_args,
        reason=reason.strip()[:1000],
        evidence_ids=refs,
        risk=spec.risk,
        action_description=spec.description,
        expected_result=spec.expected_result,
        verification_method=spec.verification_method,
        status="PROPOSED",
        created_at=_now(),
    )
    state.proposals.append(proposal)
    state.add_activity(
        "proposed",
        f"Action proposed: {spec.id} on {target}",
        reason.strip()[:500],
        evidence_ids=refs,
    )
    proposal.status = "AWAITING_APPROVAL"
    state.add_activity(
        "approval_requested",
        f"Approval requested: {spec.id} on {target}",
        f"Risk {spec.risk}. Approval expires {APPROVAL_TTL_S // 60} minutes after being granted and is single-use.",
        evidence_ids=refs,
    )
    return proposal


def approve(state: Any, proposal_id: str) -> str:
    import secrets

    proposal = _find(state, proposal_id)
    reissue = (
        proposal.status == "APPROVED"
        and proposal.decision == "approved"
        and not proposal.approval_used
    )
    if not reissue and (proposal.status != "AWAITING_APPROVAL" or proposal.decision is not None):
        raise ApprovalError("Proposal is not awaiting approval.")
    get_action(proposal.action_id)  # still registered?
    token = secrets.token_urlsafe(24)
    proposal.approval_token_hash = token_hash(token)
    proposal.approval_expires_at = _now().timestamp() + APPROVAL_TTL_S
    proposal.approval_used = False
    proposal.approval_args_hash = args_hash(proposal.args)
    proposal.decision = "approved"
    proposal.decided_at = _now()
    proposal.status = "APPROVED"
    if reissue:
        state.add_activity("approved", f"Approval re-issued: {proposal.action_id} on {proposal.target}", "Previous token was never used; a fresh single-use token replaces it.")
    else:
        state.add_activity("approved", f"Action approved: {proposal.action_id} on {proposal.target}", "Single-use approval token issued; exact arguments bound.")
    # Digest AFTER recording the approval: the consume-time comparison must see
    # the same counters, so only later evidence/conclusion changes invalidate it.
    proposal.approval_digest = investigation_digest(
        state.ev_counter, state.seq_counter, _summary(state)
    )
    return token


def reject(state: Any, proposal_id: str, reason: str = "") -> None:
    proposal = _find(state, proposal_id)
    if proposal.status != "AWAITING_APPROVAL" or proposal.decision is not None:
        raise ApprovalError("Proposal is not awaiting approval.")
    proposal.decision = "rejected"
    proposal.decided_at = _now()
    proposal.status = "REJECTED"
    state.add_activity(
        "rejected",
        f"Action rejected: {proposal.action_id} on {proposal.target}",
        (reason.strip()[:500] or "System left unchanged."),
    )


def consume_approval(state: Any, proposal_id: str, token: str, args: object) -> None:
    """Validate an execution attempt; transitions APPROVED -> EXECUTING."""
    proposal = _find(state, proposal_id)
    if proposal.status != "APPROVED" or proposal.decision != "approved":
        raise ApprovalError("No valid approval for this execution.")
    if not proposal.approval_token_hash or token_hash(token or "") != proposal.approval_token_hash:
        raise ApprovalError("Approval token mismatch.")
    if proposal.approval_used:
        raise ApprovalError("Approval token was already used (replay rejected).")
    if _now().timestamp() > (proposal.approval_expires_at or 0):
        proposal.status = "AWAITING_APPROVAL"
        proposal.decision = None
        proposal.decided_at = None
        proposal.approval_token_hash = None
        proposal.approval_used = False
        state.add_activity(
            "approval_requested",
            "Approval expired",
            "The single-use approval lapsed; review and approve again to proceed.",
        )
        raise ApprovalError("Approval has expired; re-approval required.")
    if not isinstance(args, dict) or args_hash(args) != proposal.approval_args_hash:
        raise ApprovalError("Action arguments differ from the approved set.")
    current = investigation_digest(state.ev_counter, state.seq_counter, _summary(state))
    if current != proposal.approval_digest:
        proposal.status = "AWAITING_APPROVAL"
        proposal.decision = None
        proposal.decided_at = None
        proposal.approval_token_hash = None
        proposal.approval_used = False
        state.add_activity(
            "approval_requested",
            "Approval invalidated: investigation changed",
            "Evidence or conclusions changed since approval; a new review is required.",
        )
        raise ApprovalError("Investigation changed since approval; re-approval required.")
    get_action(proposal.action_id)  # check 9: still registered and, below, enabled
    from .policies import actions_enabled

    if not actions_enabled():
        raise ApprovalError("Corrective actions are disabled.")
    proposal.approval_used = True
    proposal.status = "EXECUTING"


def _find(state: Any, proposal_id: str) -> ActionProposal:
    for proposal in state.proposals:
        if proposal.proposal_id == proposal_id:
            return proposal
    raise ApprovalError(f"Unknown proposal {proposal_id!r}.")


def _summary(state: Any) -> str | None:
    assessment = state.assessment
    return assessment.summary if assessment is not None else None
