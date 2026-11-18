"""M033-G: link model-proposed hypothesis transitions to existing sources.

A valid ID proves only that a source exists, NOT that the source supports
the inference. Require-review mode holds model-proposed downgrades for the
technician's existing explicit judgment path; observe is non-invasive.

All processing is local, deterministic, bounded, and makes zero model calls.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..knowledge.redact import redact_text
from ..schemas import HypothesisDecisionRecord
from .evidence_integrity import _is_host_measurement


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


def _live_host_reading(item: Any) -> bool:
    """M033-G's strict split: fixtures are not live host measurements."""
    source = str(getattr(item, "source", "") or "").casefold()
    if any(tag in source for tag in ("fixture", "simulated", "mock")):
        return False
    return _is_host_measurement(item)


def technician_report_refs(messages: Sequence[Mapping[str, Any]]) -> list[str]:
    """Stable message-order references, not synthetic measured evidence."""
    return [
        f"report:{index}"
        for index, msg in enumerate(messages)
        if msg.get("role") == "user"
        and isinstance(msg.get("content"), str)
        and bool(msg["content"].strip())
    ]


def review_hypothesis_changes(
    proposed: dict[str, Any] | None,
    *,
    hypotheses: Sequence[Any],
    evidence: Sequence[Any],
    messages: Sequence[Mapping[str, Any]],
    round_no: int,
    start_index: int,
    mode: str,
    target: str,
) -> tuple[dict[str, Any] | None, list[HypothesisDecisionRecord]]:
    """Validate source IDs and record proposals without asserting causality."""
    if proposed is None or mode == "off":
        return proposed, []
    pending = proposed.get("weakened")
    if not isinstance(pending, list):
        if mode == "require_review":
            sanitized = dict(proposed)
            sanitized["weakened"] = []
            return sanitized, []
        return proposed, []
    existing = {_key(str(h.title)): h for h in hypotheses}
    known = {str(e.id): e for e in evidence}
    superseded = {
        str(e.refresh_of) for e in evidence
        if getattr(e, "refresh_of", None)
    }
    reports = set(technician_report_refs(messages))
    raw_links = proposed.get("decision_links")
    links: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_links, list):
        for link in raw_links[:8]:
            if not isinstance(link, dict):
                continue
            title = link.get("hypothesis")
            if isinstance(title, str) and _key(title) not in links:
                links[_key(title)] = link

    records: list[HypothesisDecisionRecord] = []
    seen: set[str] = set()
    for title in pending[:8]:
        if not isinstance(title, str):
            continue
        key = _key(title)
        if key in seen or key not in existing:
            continue
        seen.add(key)
        hyp = existing[key]
        link = links.get(key) or {}
        evidence_ids: list[str] = []
        measured: list[str] = []
        report_refs: list[str] = []
        rejected: list[str] = []

        raw_evidence = link.get("evidence_ids")
        if isinstance(raw_evidence, list):
            for candidate in raw_evidence[:8]:
                if not isinstance(candidate, str) or len(candidate) > 60:
                    rejected.append("malformed-evidence-ref")
                    continue
                if candidate in evidence_ids:
                    continue
                item = known.get(candidate)
                if item is None:
                    rejected.append("unknown-evidence-ref")
                elif getattr(item, "error", None) or not getattr(item, "data", None):
                    rejected.append("failed-or-empty-collection-ref")
                elif candidate in superseded:
                    rejected.append("superseded-evidence-ref")
                elif target != "local" and _live_host_reading(item):
                    rejected.append("wrong-host-ref")
                else:
                    evidence_ids.append(candidate)
                    if _live_host_reading(item):
                        measured.append(candidate)

        raw_reports = link.get("report_refs")
        if isinstance(raw_reports, list):
            for candidate in raw_reports[:8]:
                if not isinstance(candidate, str) or len(candidate) > 60:
                    rejected.append("malformed-report-ref")
                elif candidate in reports and candidate not in report_refs:
                    report_refs.append(candidate)
                elif candidate not in reports:
                    rejected.append("unknown-report-ref")

        if rejected:
            status = "invalid"
        elif evidence_ids and report_refs:
            status = "mixed"
        elif evidence_ids:
            status = "evidence_cited"
        elif report_refs:
            status = "report_only"
        else:
            status = "uncited"

        raw_reason = link.get("why")
        reason = redact_text(raw_reason.strip())[:500] if isinstance(raw_reason, str) else ""
        note = (
            "References were found, but causal support is unverified; "
            "technician judgment remains authoritative."
            if evidence_ids or report_refs
            else "No valid supporting source was cited for this model proposal."
        )
        record = HypothesisDecisionRecord(
            decision_id=f"decision-{start_index + len(records) + 1}",
            round=max(0, round_no),
            hypothesis_id=hyp.hypothesis_id,
            hypothesis_title=hyp.title,
            proposed_status="weakened",
            reason=reason,
            evidence_ids=evidence_ids,
            measured_evidence_ids=measured,
            report_refs=report_refs,
            rejected_refs=list(dict.fromkeys(rejected)),
            link_status=status,
            review_state="pending_technician" if mode == "require_review" else "observed",
            provenance_note=note,
        )
        records.append(record)

    if mode == "require_review":
        sanitized = dict(proposed)
        # Preserve original JSON and proposed wording in the decision ledger.
        # No model-proposed weakening becomes a state transition until the
        # existing manual /hypotheses/.../status technician route is used.
        sanitized["weakened"] = []
        return sanitized, records
    return proposed, records
