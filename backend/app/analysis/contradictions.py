"""Deterministic contradiction detection between observations.

Rules compare measured values only — never model text — and every hit cites
the evidence ids involved. Wording stays hedged ("appears to contradict")
because fixtures are per-tool snapshots and live readings can race: a hit is
a prompt to re-check, not proof of fault.
"""

from __future__ import annotations

from ..schemas import Contradiction, EvidenceItem

# Report phrases that claim the network path itself is down (as opposed to a
# single site or a VPN tunnel, which can fail while adapters stay Up).
NET_DOWN_PHRASES = (
    "network is down",
    "network down",
    "no network",
    "cable is unplugged",
    "cable unplugged",
    "no connectivity",
    "not connected",
    "adapter is unavailable",
)


def _usable_by_category(evidence: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
    grouped: dict[str, list[EvidenceItem]] = {}
    for item in evidence:
        if item.error is not None:
            continue
        grouped.setdefault(item.category, []).append(item)
    return grouped


def _service_process_conflicts(
    grouped: dict[str, list[EvidenceItem]],
) -> list[Contradiction]:
    hits: list[Contradiction] = []
    details = grouped.get("service_details", [])
    procs = grouped.get("process_info", [])
    if not details or not procs:
        return hits
    for detail in details:
        name = str(detail.data.get("name", "") or "").lower()
        if not name:
            continue
        status = detail.data.get("status", {})
        state = str(status.get("status", "") or "").lower() if isinstance(status, dict) else ""
        for proc in procs:
            service = proc.data.get("service") or {}
            if not isinstance(service, dict):
                continue
            if str(service.get("name", "") or "").lower() != name:
                continue
            found = bool(proc.data.get("found"))
            if state == "stopped" and found:
                hits.append(
                    Contradiction(
                        contradiction_id=f"cx-svcproc-{detail.id}-{proc.id}",
                        evidence_ids=[detail.id, proc.id],
                        description=(
                            f"Service '{service.get('name')}' reports Stopped ({detail.id}) "
                            f"but a live hosting process was found ({proc.id}). One of the "
                            "two readings may be stale, or the process hosts other services."
                        ),
                    )
                )
            elif state == "running" and not found:
                hits.append(
                    Contradiction(
                        contradiction_id=f"cx-svcproc-{detail.id}-{proc.id}",
                        evidence_ids=[detail.id, proc.id],
                        description=(
                            f"Service '{service.get('name')}' reports Running ({detail.id}) "
                            f"but no hosting process was found ({proc.id}). Re-check both "
                            "before concluding anything."
                        ),
                    )
                )
    return hits


def _network_report_conflicts(
    problem: str, grouped: dict[str, list[EvidenceItem]]
) -> list[Contradiction]:
    lowered = problem.lower()
    if not any(phrase in lowered for phrase in NET_DOWN_PHRASES):
        return []
    adapters = grouped.get("net_adapters", [])
    if not adapters:
        return []
    latest = adapters[-1]
    rows = latest.data.get("adapters", [])
    if not isinstance(rows, list) or not rows:
        return []
    up = [
        str(row.get("name", "?"))
        for row in rows
        if isinstance(row, dict) and str(row.get("status", "") or "").lower() == "up"
    ]
    if not up:
        return []
    return [
        Contradiction(
            contradiction_id=f"cx-netreport-{latest.id}",
            evidence_ids=[latest.id],
            description=(
                "The report describes the network path as down, but measurement "
                f"({latest.id}) shows adapter(s) Up: {', '.join(up[:3])}. Trust the "
                "measurement over the report, or re-check if the state may have changed."
            ),
        )
    ]


def _dns_conflicts(grouped: dict[str, list[EvidenceItem]]) -> list[Contradiction]:
    configs = grouped.get("dns_config", [])
    tests = grouped.get("dns_test", [])
    if not configs or not tests:
        return []
    config = configs[-1]
    test = tests[-1]
    interfaces = config.data.get("interfaces", [])
    if not isinstance(interfaces, list):
        return []
    configured = [
        iface
        for iface in interfaces
        if isinstance(iface, dict) and (iface.get("servers") or iface.get("dns_servers"))
    ]
    succeeded = bool(test.data.get("succeeded"))
    if configured and not succeeded:
        return [
            Contradiction(
                contradiction_id=f"cx-dns-{config.id}-{test.id}",
                evidence_ids=[config.id, test.id],
                description=(
                    f"DNS servers are configured ({config.id}) but the bounded control "
                    f"query failed ({test.id}). The resolver path, not the "
                    "configuration, is suspect — or the test target differs from the "
                    "failing host."
                ),
            )
        ]
    if not configured and succeeded:
        return [
            Contradiction(
                contradiction_id=f"cx-dns-{config.id}-{test.id}",
                evidence_ids=[config.id, test.id],
                description=(
                    f"No DNS servers appear configured ({config.id}) yet the control "
                    f"query succeeded ({test.id}). One reading may be stale or scoped "
                    "to a different interface."
                ),
            )
        ]
    return []


def _worker_conflicts(grouped: dict[str, list[EvidenceItem]]) -> list[Contradiction]:
    workers = grouped.get("demo_worker", [])
    if not workers:
        return []
    latest = workers[-1]
    status = str(latest.data.get("status", "") or "")
    age = latest.data.get("heartbeat_age_s")
    if status == "healthy" and isinstance(age, (int, float)) and age > 120:
        return [
            Contradiction(
                contradiction_id=f"cx-worker-{latest.id}",
                evidence_ids=[latest.id],
                description=(
                    f"Demo worker reports healthy but its heartbeat is {age:g}s old "
                    f"({latest.id}). The status line may be stale."
                ),
            )
        ]
    return []


def detect_contradictions(
    problem: str, evidence: list[EvidenceItem]
) -> list[Contradiction]:
    """Run every deterministic rule; order is stable for tests and UI."""
    grouped = _usable_by_category(evidence)
    hits: list[Contradiction] = []
    hits.extend(_service_process_conflicts(grouped))
    hits.extend(_network_report_conflicts(problem, grouped))
    hits.extend(_dns_conflicts(grouped))
    hits.extend(_worker_conflicts(grouped))
    return hits
