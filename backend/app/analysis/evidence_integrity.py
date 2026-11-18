"""M033-F: evidence provenance and unsupported inference review.

No diagnosis, model invocation or policy decision is performed here.
Findings are triage hints for a technician: language may be misleading or
evidence insufficient. A finding NEVER proves the proposed claim false.

All output details are fixed controlled strings, not private evidence or
technician text. The original model response is never mutated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Provenance:
    """Non-sensitive counters for evidence actually available this round."""

    measured_host_items: int
    failed_host_items: int
    non_host_items: int
    technician_report_present: bool


@dataclass(frozen=True)
class IntegrityFinding:
    code: str
    severity: str
    detail: str


# The patterns are deliberately specific; a negative or speculative
# statement must not be flagged as a positive measurement. We err toward
# "not enough to assess" rather than broad automatic censorship.
_MULTIPLE_DEVICES = re.compile(
    r"\b(?:multiple|several|two|different|both)\s+(?:\w+\s+){0,2}"
    r"(?:devices|machines|computers|laptops|pcs)\b",
    re.IGNORECASE,
)
_CLAIM_CONTEXT = re.compile(
    r"\b(?:across|on|tested|confirmed|reproduced|observed|affects?|"
    r"consistent|working|failing|failed)\b",
    re.IGNORECASE,
)
_PING = re.compile(r"\b(?:ping|pinging|icmp)\b", re.IGNORECASE)
_TIMEOUT = re.compile(
    r"\b(?:timed?\s*out|times?\s*out|timeout|unreachable|"
    r"no\s+reply|no\s+response|100%\s+loss|packet\s+loss)\b",
    re.IGNORECASE,
)
_SERVICE_CERTAINTY = re.compile(
    r"\b(?:license|licensing|application|app|service|server)\b.{0,100}"
    r"\b(?:is|was|are|were|has been)\s+"
    r"(?:down|offline|unreachable|unavailable|broken|not running)\b",
    re.IGNORECASE,
)
_CAUSAL_CERTAINTY = re.compile(
    r"\b(?:due to|caused by|proves?|confirms?|definitely|"
    r"therefore|must be|is caused by)\b",
    re.IGNORECASE,
)
_UNCERTAIN = re.compile(
    r"\b(?:may|might|could|possibly|potentially|not confirmed|"
    r"unverified|cannot conclude|does not prove|not enough)\b",
    re.IGNORECASE,
)
_NEW_CHANGE = re.compile(
    r"\b(?:installed|installation|updated|update|upgraded|"
    r"changed|replaced|introduced|added|new|rollout|deployed)\b",
    re.IGNORECASE,
)
_CLEAR_NEGATION = re.compile(
    r"\b(?:resolved|fixed|removed|rolled back|uninstalled|reverted|"
    r"no longer|without|ruled out|disproved|did not occur)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOP = frozenset(
    "a an the that this those these from with for or and about have has "
    "being problem issue failure broken conflict software hardware system "
    "work working when where after before user users device devices "
    "check server application apps network change".split()
)


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.casefold())
            if len(w) >= 4 and w not in _STOP}


def _is_host_measurement(item: Any) -> bool:
    source = str(getattr(item, "source", "") or "")
    tool_name = getattr(item, "tool_name", None)
    category = str(getattr(item, "category", "") or "")
    return (
        (source.startswith("tool:") or source.startswith("powershell:"))
        and bool(tool_name or category)
        and not source.startswith("tool:fixture:")
    )


def summarize_sources(evidence: Iterable[Any], observation: str) -> Provenance:
    measured = failed = other = 0
    for item in evidence:
        if _is_host_measurement(item):
            # Errors or missing values are not successful observations.
            if getattr(item, "error", None) or not getattr(item, "data", None):
                failed += 1
            else:
                measured += 1
        else:
            other += 1
    return Provenance(
        measured_host_items=measured,
        failed_host_items=failed,
        non_host_items=other,
        technician_report_present=bool(observation.strip()),
    )


def _has_new_service_measurement(evidence: Iterable[Any], new_ids: set[str]) -> bool:
    """Only service-specific diagnostics can partially corroborate service status.

    Ordinary OS data, successful ping, or device configuration on a different
    machine does NOT establish application-service health.
    """
    if not new_ids:
        return False
    return any(
        str(getattr(item, "id", "") or "") in new_ids
        and _is_host_measurement(item)
        and str(getattr(item, "category", "")).lower() in {
            "service_status", "service_health", "port_status", "tcp_port",
            "endpoint_health",
        }
        and not getattr(item, "error", None)
        and bool(getattr(item, "data", None))
        for item in evidence
    )


def audit_reassessment(
    reassess: Mapping[str, Any] | None,
    *,
    problem: str,
    observation: str,
    evidence: Iterable[Any] = (),
    new_evidence_ids: set[str] | None = None,
    prior_reports: Iterable[str] = (),
) -> tuple[IntegrityFinding, ...]:
    """Review *claims* against available inputs, never edit model output.

    A host/device assertion must be grounded in a matching report. Evidence
    counts alone cannot establish physical host identities. Only a *fresh,
    service-specific* measurement can partially support a service-status
    statement, not a separate root-cause attribution.
    """
    if not reassess:
        return ()
    evidence_items = tuple(evidence)
    has_new_service_measurement = _has_new_service_measurement(
        evidence_items, new_evidence_ids or set()
    )
    recent_reports = " ".join((problem, observation, *list(prior_reports)[-8:]))
    verdict = str(reassess.get("verdict") or "")[:1000]
    findings: list[IntegrityFinding] = []

    # Broad cardinality claim such as "across multiple devices" when only
    # different applications on one laptop have been described.
    if (_MULTIPLE_DEVICES.search(verdict)
            and _CLAIM_CONTEXT.search(verdict)
            and not _MULTIPLE_DEVICES.search(recent_reports)
            and not _UNCERTAIN.search(verdict)):
        findings.append(IntegrityFinding(
            "unverified-multi-host-claim", "review",
            "A claim about multiple devices needs distinct host-level observations.",
        ))

    # ICMP is useful for network reachability, never decisive proof of
    # application-service availability or the root cause of its outage.
    if (_PING.search(recent_reports)
            and _TIMEOUT.search(recent_reports)
            and (_SERVICE_CERTAINTY.search(verdict)
                 or (_CAUSAL_CERTAINTY.search(verdict)
                     and re.search(r"\b(?:server|service|licens\w*)\b",
                                   verdict, re.IGNORECASE)))
            and not _UNCERTAIN.search(verdict)
            and (
                not has_new_service_measurement
                or _CAUSAL_CERTAINTY.search(verdict)
            )):
        findings.append(IntegrityFinding(
            "icmp-not-service-proof", "review",
            "ICMP reachability does not verify an application's service or its cause.",
        ))

    # Correlation is not causation; neither is it disproof. If the same
    # salient technical component has just been installed/changed, a model
    # downgrade needs explicit contradictory observation, not confidence.
    weakened_raw = reassess.get("weakened") or []
    weakened = weakened_raw[:8] if isinstance(weakened_raw, list) else []
    recent = " ".join((observation, *list(prior_reports)[-2:]))
    if _NEW_CHANGE.search(observation) and not _CLEAR_NEGATION.search(recent):
        observation_terms = _words(observation)
        for title in weakened:
            shared = observation_terms & _words(str(title))
            if shared:
                findings.append(IntegrityFinding(
                    "correlated-change-weakened", "review",
                    "A recently reported change shares a component with a weakened "
                    "hypothesis; inspect the contradictory evidence before downgrading.",
                ))
                break

    return tuple(findings)


def format_audit_note(findings: Iterable[IntegrityFinding]) -> str:
    """Safe for activity log: controlled codes, no user text or secret data."""
    codes = tuple(f.code for f in findings)
    return (
        "Potential evidence/claim mismatch: " + ", ".join(codes[:4])
        + ". Review required; no hypothesis status changed by this audit."
    )
