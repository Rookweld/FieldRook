"""M040: Bounded checks on technician-reported technical failure layers.

This is NOT a host diagnostic collector and does not run commands. It extracts
narrow, verifiable relationships from one technician report at a time. All
findings remain labelled *reported*, never measurements by FieldRook.
Unknown or contradictory reports must not be presented as confirmed causes.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_BIND_PORT = re.compile(
    r"(?:listen\s+tcp\s+(?:127\.0\.0\.1|localhost|0\.0\.0\.0|::1):|"
    r"\bbind(?:ing)?\s+(?:to|on)\s+(?:port\s*)?|\bport\s+)"
    r"(?P<port>\d{2,5})\b",
    re.IGNORECASE,
)
_DENIED = re.compile(
    r"\b(?:access\s+(?:is\s+)?denied|permission(?:s)?\s+denied|"
    r"forbidden\s+by\s+(?:its\s+)?access\s+permissions|"
    r"access\s+permission\s+violation|WSAEACCES|EACCES)\b",
    re.IGNORECASE,
)
_EXCLUDED_RANGE = re.compile(
    r"\b(?:excluded|reserved)\s+(?:TCP\s+)?(?:port\s+)?(?:range\s+)?"
    r"(?P<first>\d{2,5})\s*[-â€“]\s*(?P<last>\d{2,5})\b",
    re.IGNORECASE,
)
_LISTENER_ABSENT = re.compile(
    r"\b(?:no\s+(?:process|other\s+process|listener)\s+(?:is\s+)?"
    r"(?:currently\s+)?listen(?:ing|s)?|nothing\s+(?:is\s+)?listening|"
    r"no\s+process\s+is\s+listening)\b",
    re.IGNORECASE,
)

# Ordered classes, not raw model/output strings. A failure can have more
# than one cause; do not collapse chronological blockers into a single guess.
_LAYERS = (
    ("module-import", re.compile(
        r"\b(?:ConvertTo-SecureString|Import-Module)\b.*?"
        r"(?:module|could\s+not\s+be\s+loaded|type\s+members)"
        r"|\bMicrosoft\.PowerShell\.Security\b.*?"
        r"(?:fail|type|module|error)", re.IGNORECASE | re.DOTALL,
    ), "PowerShell module import failed"),
    ("profile-lookup", re.compile(
        r"(?:\b(?:profile|yaml)\b.{0,220}\b(?:missing|not\s+found|cannot\s+find|"
        r"can't\s+find|does\s+not\s+exist|cannot\s+locate|"
        r"wrong\s+path)\b|"
        r"\b(?:cannot\s+find|can't\s+find|not\s+found|cannot\s+locate)\b"
        r".{0,120}\b(?:profile|yaml)\b)",
        re.IGNORECASE | re.DOTALL,
    ), "configuration/profile lookup failed"),
    ("port-bind", re.compile(
        r"\b(?:listen\s+tcp|bind(?:ing)?)\b.*?"
        r"(?:access\s+(?:is\s+)?denied|forbidden|permission\s+violation|"
        r"WSAEACCES|EACCES)",
        re.IGNORECASE | re.DOTALL,
    ), "local TCP listener could not bind"),
)


@dataclass(frozen=True)
class ExcludedPortReport:
    port: int
    range_start: int
    range_end: int
    no_listener_reported: bool

    def prompt_note(self) -> str:
        return (
            "Technician report (not a FieldRook measurement): TCP bind port "
            f"{self.port} access denied; excluded Windows TCP port interval "
            f"{self.range_start}-{self.range_end} contains {self.port}. "
            "A Windows port reservation is better supported than a generic "
            "firewall or competing-listener guess. Verify on the affected "
            "machine; do not change port exclusions automatically."
        )

    def display_note(self) -> str:
        listener = (
            " The technician also reports no listening process."
            if self.no_listener_reported else ""
        )
        return (
            "Technician-reported port evidence (not a FieldRook measurement): "
            f"TCP bind {self.port} denied; excluded interval "
            f"{self.range_start}-{self.range_end} contains that port."
            f"{listener} This supports investigating Windows port reservation "
            "before blaming a firewall or competing listener; independently "
            "verify on the affected machine."
        )


def excluded_port_from_reports(reports: Iterable[str]) -> ExcludedPortReport | None:
    """Only match access-denied binds and ranges in the SAME report.

    Bare excluded-port ranges, arbitrary lists of numbers, a service refusing
    a connection, non-overlapping exclusions, or merely seeing port 8080 must
    never imply this diagnosis. Scan recent reports newest first.
    """
    for report in reversed(tuple(reports)[-12:]):
        text = str(report or "")[:3000]
        if not _DENIED.search(text) or not re.search(
            r"\b(?:bind|listen\s+tcp)\b", text, re.IGNORECASE
        ):
            continue
        found_port = _BIND_PORT.search(text)
        if not found_port:
            continue
        port = int(found_port.group("port"))
        if not 1 <= port <= 65535:
            continue
        for matched in _EXCLUDED_RANGE.finditer(text):
            start, end = int(matched.group("first")), int(matched.group("last"))
            if 1 <= start <= port <= end <= 65535:
                return ExcludedPortReport(
                    port=port, range_start=start, range_end=end,
                    no_listener_reported=bool(_LISTENER_ABSENT.search(text)),
                )
    return None


def reported_failure_layers(reports: Iterable[str]) -> tuple[str, ...]:
    """Concise chronological labels. No raw report content or private values."""
    seen: set[str] = set()
    layers: list[str] = []
    for report in tuple(reports)[-12:]:
        text = str(report or "")[:3000]
        for code, pattern, label in _LAYERS:
            if code not in seen and pattern.search(text):
                seen.add(code)
                layers.append(label)
    return tuple(layers)


def reported_context(reports: Iterable[str]) -> str:
    """Short UI statement; intentionally not a diagnosis or assertion of truth."""
    items = tuple(reports)[-12:]
    layers = reported_failure_layers(items)
    port = excluded_port_from_reports(items)
    parts: list[str] = []
    if len(layers) >= 2:
        parts.append(
            "Sequential failure layers in technician reports (not independent "
            "host measurements): " + "; ".join(layers[:4]) + ". "
            "Resolving one blocker can reveal another."
        )
    if port:
        parts.append(port.display_note())
    return " ".join(parts)[:1100]
