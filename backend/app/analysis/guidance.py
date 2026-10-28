"""M019 guidance safety filter: deterministic impact classification.

Model-suggested troubleshooting steps are untrusted guidance. This module
classifies every plan step and runbook step by impact so the UI can badge
risk honestly and technicians never mistake a disruptive or unsupported
suggestion for an ordinary read-only check:

- READ_ONLY: a registered FieldRook tool performs a bounded read.
- MANUAL_INFORMATION: the technician gathers information (no state change).
- SYSTEM_CHANGE: the step modifies settings, services, files, or software.
- PRIVILEGED_ACTION: the step needs elevation or admin rights.
- POTENTIALLY_DISRUPTIVE: the step can interrupt work or damage data
  (reboots, disk repair, registry edits, OS recovery).
- UNSUPPORTED_OR_UNSAFE: no registered tool can do this, or the text
  matches a known-unsafe pattern (security bypass, destructive commands).

The filter is advisory only: it labels guidance and raises warnings. It
never authorizes execution — actual tool calls still pass the registry,
and real actions still need approve/execute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import GuidanceImpact

# Ordered most-severe first; the first matching tier wins.
_TIERS: list[tuple[GuidanceImpact, list[tuple[str, str]]]] = [
    (
        "UNSUPPORTED_OR_UNSAFE",
        [
            (r"creat\w*\s+(an?\s+)?(admin\w*|privileged)\s+account", "creating a privileged account to bypass access limits"),
            (r"\bbypass\b", "bypassing a security control"),
            (r"disable\s+(windows\s+)?defender", "disabling Defender"),
            (r"disable\s+(the\s+)?firewall", "disabling the firewall"),
            (r"turn\s+off\s+.{0,40}(defender|firewall|antivirus|uac)", "turning off a security control"),
            (r"disable\s+uac", "disabling UAC"),
            (r"take\s+ownership", "taking ownership of protected files"),
            (r"format\s+[a-z]\s*:", "formatting a drive"),
            (r"\bdiskpart\b", "diskpart (destructive when misused)"),
            (r"\brm\s+-rf?\b", "recursive forced deletion"),
            (r"\bdel\s+/[sq]", "recursive forced deletion"),
            (r"disable\s+.{0,20}backup", "disabling backups"),
            (r"\bkeygen\b|\bcrack\b.{0,20}(windows|office|license)|pirat", "unlicensed software"),
        ],
    ),
    (
        "POTENTIALLY_DISRUPTIVE",
        [
            (r"chkdsk\s+/[fr]", "chkdsk with repair (locks the volume, may reboot)"),
            (r"reset\s+(this\s+)?pc|factory\s+reset|reinstall\s+windows", "OS reset/reinstall"),
            (r"system\s+restore", "System Restore (rolls back system state)"),
            (r"bios\s+update|firmware\s+update|uefi\s+update", "firmware update"),
            (r"reg\s+(add|delete|edit)|regedit.{0,20}(edit|change|delete)|registry\s+(edit|change|delete|writ|modif)", "registry modification"),
            (r"reboot|shutdown\s+/[rs]|restart\s+(the\s+)?(computer|laptop|pc|server|machine|system)\b", "rebooting the machine"),
            (r"driver.{0,20}(reinstall|uninstall|rollback)|reinstall.{0,20}driver", "driver reinstall/uninstall"),
            (r"\bdefrag\b|disk\s+defragment", "disk defragmentation (long, heavy I/O)"),
        ],
    ),
    (
        "PRIVILEGED_ACTION",
        [
            (r"as\s+administrator|elevated|runas\b", "an elevated prompt"),
            (r"admin\w*\s+(rights|privileges|password|credentials|consent)", "administrator rights"),
            (r"group\s+policy|gpedit", "Group Policy changes"),
            (r"\binstall\b.{0,30}(driver|software|application|update|kb\d+)|install\s+(the\s+)?(latest|new)", "installing software"),
            (r"credential|admin\w*\s+account\s+(password|reset|enabl)", "credential or admin-account changes"),
        ],
    ),
    (
        "SYSTEM_CHANGE",
        [
            (r"restart\s+.{0,30}service|service.{0,20}restart", "restarting a service"),
            (r"\bsfc\b|dism\b", "system file repair"),
            (r"\bflushdns\b|ipconfig\s+/(flush|register|release|renew)", "resetting network state"),
            (r"\breinstall\b|\buninstall\b", "installing/removing software"),
            (r"change\s+.{0,30}(setting|dns|config|startup|policy)", "changing configuration"),
            (r"clear\s+.{0,20}cache|delete\s+.{0,20}(cache|temp|temporary)", "clearing cached data"),
            (r"enabl\w+\s+.{0,20}service|start\s+.{0,20}service|stop\s+.{0,20}service|set\s+.{0,20}service", "changing a service"),
            (r"repair\s+.{0,20}(install|office|app|installation)", "repairing an installation"),
            (r"update\s+.{0,20}driver", "updating a driver"),
        ],
    ),
]

_COMPILED: list[tuple[GuidanceImpact, list[tuple[re.Pattern[str], str]]]] = [
    (tier, [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in patterns])
    for tier, patterns in _TIERS
]

_NEGATION_RE = re.compile(r"\b(do\s+not|don't|doesn't|never|avoid|shouldn't|must\s+not|without)\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?;\n]+")
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9.\-]*")

_DISK_TOKENS = frozenset(
    {"disk", "chkdsk", "defrag", "partition", "volume", "smart", "s.m.a.r.t.",
     "sector", "ssd", "hdd", "hard drive", "bad sector"}
)
_NET_TOKENS = frozenset(
    {"network", "share", "wifi", "wi-fi", "wireless", "vpn", "dns", "ethernet",
     "lan", "wan", "internet", "intranet", "nas", "smb", "mapped drive"}
)
_HOST_WORDS_RE = re.compile(
    r"\b(this computer|this pc|this machine|locally|localhost|on the host)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GuidanceVerdict:
    impact: GuidanceImpact
    safety_note: str = ""


def _tokens(text: str) -> set[str]:
    words = set(_WORD_RE.findall((text or "").lower()))
    lowered = (text or "").lower()
    if "hard drive" in lowered:
        words.add("hard drive")
    if "bad sector" in lowered:
        words.add("bad sector")
    if "mapped drive" in lowered:
        words.add("mapped drive")
    return words


def _negated(sentence: str, match_start: int) -> bool:
    return _NEGATION_RE.search(sentence, 0, match_start) is not None


def classify_guidance(
    instruction: str,
    why: str = "",
    kind: str = "TECHNICIAN_CHECK",
    tool_registered: bool = False,
    problem: str = "",
    target: str = "local",
) -> GuidanceVerdict:
    """Classify one guidance step. Deterministic; no model calls.

    Automation claimed without a registered tool is UNSUPPORTED_OR_UNSAFE:
    the registry — not the model — decides what FieldRook may execute.
    Text matches inside negated sentences ("do not disable the firewall")
    do not count. A fault-domain note is appended when a disk-targeted step
    meets a network-reading problem or vice versa.
    """
    text = f"{instruction or ''} {why or ''}".strip()
    if kind == "AUTOMATED_READ_ONLY" and not tool_registered:
        return GuidanceVerdict(
            "UNSUPPORTED_OR_UNSAFE",
            "No registered FieldRook tool performs this; treat it as manual "
            "guidance only, not a FieldRook capability.",
        )
    for tier, patterns in _COMPILED:
        for pattern, label in patterns:
            for sentence in _SENTENCE_SPLIT_RE.split(text):
                match = pattern.search(sentence)
                if match and not _negated(sentence, match.start()):
                    note = _note_for(tier, label, text)
                    relevance = _relevance_note(text, problem, target)
                    if relevance:
                        note = f"{note} {relevance}"
                    return GuidanceVerdict(tier, note)
    base: GuidanceImpact = "READ_ONLY" if tool_registered else "MANUAL_INFORMATION"
    relevance = _relevance_note(text, problem, target)
    return GuidanceVerdict(base, relevance)


def _note_for(tier: str, label: str, text: str) -> str:
    _ = text
    if tier == "UNSUPPORTED_OR_UNSAFE":
        return (
            f"Flagged as unsupported or unsafe ({label}). Do not treat this "
            "as a FieldRook capability; use your own judgment."
        )
    if tier == "POTENTIALLY_DISRUPTIVE":
        return (
            f"Potentially disruptive ({label}). Save work and confirm the "
            "impact before proceeding."
        )
    if tier == "PRIVILEGED_ACTION":
        return f"Requires elevated privileges ({label})."
    return f"Changes system state ({label}); verify before and after."


def _relevance_note(text: str, problem: str, target: str) -> str:
    notes: list[str] = []
    step_tokens = _tokens(text)
    step_disk = bool(step_tokens & _DISK_TOKENS)
    step_net = bool(step_tokens & _NET_TOKENS)
    if step_disk != step_net and problem.strip():
        problem_tokens = _tokens(problem)
        problem_disk = bool(problem_tokens & _DISK_TOKENS)
        problem_net = bool(problem_tokens & _NET_TOKENS)
        if step_disk and problem_net and not problem_disk:
            notes.append(
                "This step targets local disk, but the problem reads as "
                "network-related; confirm it applies."
            )
        elif step_net and problem_disk and not problem_net:
            notes.append(
                "This step targets the network, but the problem reads as "
                "disk-related; confirm it applies."
            )
    if target != "local" and _HOST_WORDS_RE.search(text):
        notes.append(
            "This step names the FieldRook host, but the affected machine is "
            "elsewhere; run it there instead."
        )
    return " ".join(notes)


def scan_texts_for_unsafe(texts: list[str]) -> list[str]:
    """Flag free-text guidance (next actions, explanations) that matches an
    UNSUPPORTED_OR_UNSAFE pattern outside a negated sentence. Returns short
    warning strings; empty when nothing matches."""
    findings: list[str] = []
    unsafe = next(patterns for tier, patterns in _COMPILED if tier == "UNSUPPORTED_OR_UNSAFE")
    for text in texts:
        for sentence in _SENTENCE_SPLIT_RE.split(text or ""):
            for pattern, label in unsafe:
                match = pattern.search(sentence)
                if match and not _negated(sentence, match.start()):
                    findings.append(
                        f"Flagged unsafe guidance ({label}): {sentence.strip()[:160]}"
                    )
                    break
            else:
                continue
            break
    return findings
