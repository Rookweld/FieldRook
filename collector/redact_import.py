"""Shared redaction core for collector import (FORGE contracts v1, D4/D8).

PROMOTION-READY: the lead promotes this module's core to
``backend/app/redact/`` for CHARLIE/lead reuse (D4a). Keep it clean:

- stdlib only (``re``, ``getpass``, ``hashlib``), no backend imports,
  no third-party deps, no network, no AI runtime;
- no module-level I/O; all functions pure except best-effort OS-username
  lookup (injectable via the ``username`` parameter for determinism);
- API is a superset of ``backend/app/knowledge/redact.py``:
  ``redact_text(text)`` and ``redact_value(value, max_chars)`` keep the
  same default behaviour and replacement tokens, with optional
  ``hostname``/``hint``/``username`` keyword parameters for the new
  hostname-to-hash+hint rule (D8).

Rules implemented:

- secret-like ``key[:=]value`` and ``--flag value`` pairs -> ``[secret redacted]``;
- email addresses -> ``[email redacted]``;
- ``DOMAIN\\user`` forms -> ``[user redacted]``;
- current OS username (when >= 3 chars) -> ``[user redacted]``;
- known-hostname occurrences -> ``[host <hint>]`` (or ``[host redacted]``
  when no hint was supplied); raw hostnames never persist (D8);
- command-line keys (``command_line``, ``commandline``, ``cmdline``,
  case-insensitive) are dropped to ``[cmdline dropped]`` — full command
  lines are never collected upstream and never appear in output.

Counting variants (``*_with_count`` and :func:`redact_data`) report how
many substitutions/drops were applied so the collector can record
``data.provenance.redaction_count`` (contracts 1C, D1b).
"""

from __future__ import annotations

import getpass
import hashlib
import re
from typing import Any

__all__ = [
    "SECRET_PATTERNS",
    "EMAIL_PATTERN",
    "USERID_PATTERN",
    "CMDLINE_KEYS",
    "HOST_TOKEN_NO_HINT",
    "host_token",
    "hash_hostname",
    "sanitize_hint",
    "build_identity",
    "redact_text",
    "redact_text_with_count",
    "redact_value",
    "redact_value_with_count",
    "redact_data",
]

# Same pattern set as backend/app/knowledge/redact.py (promotion source).
SECRET_PATTERNS = (
    re.compile(
        r"(?i)(password|passwd|pwd|secret|token|apikey|api_key|clientsecret)\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)--?(password|passwd|pwd|secret|token|apikey|api_key)\s+\S+"),
)
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
USERID_PATTERN = re.compile(r"\b[A-Za-z0-9._-]{2,}\\[A-Za-z0-9._$-]{2,}\b")

# Keys whose values are command lines and must never persist (lowercased).
CMDLINE_KEYS = frozenset({"command_line", "commandline", "cmdline"})

HOST_TOKEN_NO_HINT = "[host redacted]"


def host_token(hint: str | None) -> str:
    """Replacement token for a redacted hostname occurrence."""
    clean = (hint or "").strip()
    if clean:
        return f"[host {clean}]"
    return HOST_TOKEN_NO_HINT


def _os_username() -> str:
    try:
        return getpass.getuser().strip()
    except Exception:  # noqa: BLE001 - best effort
        return ""


def hash_hostname(hostname: str) -> str:
    """SHA-256 hex of a hostname (lowercased, stripped) for D8 identity."""
    return hashlib.sha256((hostname or "").strip().lower().encode("utf-8")).hexdigest()


def sanitize_hint(hint: str | None, hostname: str = "") -> str | None:
    """Validate a technician label: never the raw hostname (D8).

    Returns the stripped hint, or ``None`` when empty. Raises
    :class:`ValueError` when the hint equals the hostname
    (case-insensitive) or contains it.
    """
    if hint is None:
        return None
    clean = hint.strip()
    if not clean:
        return None
    if len(clean) > 128:
        raise ValueError("target_hint must be <= 128 characters.")
    host = (hostname or "").strip().lower()
    lowered = clean.lower()
    if host and (lowered == host or host in lowered):
        raise ValueError("target_hint must never be or contain the raw hostname.")
    return clean


def build_identity(hostname: str, hint: str | None = None) -> dict[str, str | None]:
    """Build the D8 identity pair ``{hostname_hash, target_hint}``."""
    if not (hostname or "").strip():
        raise ValueError("hostname is required to build collector identity.")
    return {
        "hostname_hash": hash_hostname(hostname),
        "target_hint": sanitize_hint(hint, hostname),
    }


def _subn_all(text: str, hostname: str, hint: str | None, username: str) -> tuple[str, int]:
    count = 0
    cleaned = text or ""
    for pattern in SECRET_PATTERNS:
        cleaned, n = pattern.subn("[secret redacted]", cleaned)
        count += n
    cleaned, n = EMAIL_PATTERN.subn("[email redacted]", cleaned)
    count += n
    cleaned, n = USERID_PATTERN.subn("[user redacted]", cleaned)
    count += n
    host = (hostname or "").strip()
    if host:
        cleaned, n = re.subn(re.escape(host), host_token(hint), cleaned, flags=re.IGNORECASE)
        count += n
    user = (username or "").strip()
    if user and len(user) >= 3:
        cleaned, n = re.subn(re.escape(user), "[user redacted]", cleaned, flags=re.IGNORECASE)
        count += n
    return cleaned, count


def redact_text_with_count(
    text: str,
    hostname: str = "",
    hint: str | None = None,
    username: str | None = None,
) -> tuple[str, int]:
    """Redact ``text``; return ``(redacted, substitution_count)``.

    ``username`` defaults to the current OS user (best effort); pass
    ``""`` to disable username masking (deterministic tests) or an
    explicit name to mask.
    """
    user = _os_username() if username is None else (username or "")
    redacted, count = _subn_all(text or "", hostname, hint, user)
    return redacted, count


def redact_text(
    text: str,
    hostname: str = "",
    hint: str | None = None,
    username: str | None = None,
) -> str:
    """Redact ``text`` (backend-compatible default behaviour)."""
    redacted, _ = redact_text_with_count(text, hostname, hint, username)
    return redacted


def _shorten(text: str, max_chars: int) -> str:
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


def redact_value_with_count(
    value: object,
    max_chars: int = 200,
    hostname: str = "",
    hint: str | None = None,
    username: str | None = None,
) -> tuple[str, int]:
    """Backend-compatible scalar redaction plus a substitution count."""
    user = _os_username() if username is None else (username or "")
    if value is None:
        return "", 0
    if isinstance(value, bool):
        return ("true" if value else "false"), 0
    if isinstance(value, (int, float)):
        return str(value), 0
    if isinstance(value, (list, tuple)):
        parts: list[str] = []
        total = 0
        for item in list(value)[:8]:
            text, n = redact_value_with_count(item, 60, hostname, hint, user)
            parts.append(text)
            total += n
        return "[" + ", ".join(parts) + "]", total
    redacted, count = _subn_all(str(value), hostname, hint, user)
    cleaned = _shorten(redacted.strip().replace("\n", " "), max_chars)
    return cleaned, count


def redact_value(
    value: object,
    max_chars: int = 200,
    hostname: str = "",
    hint: str | None = None,
    username: str | None = None,
) -> str:
    """Redact a scalar (backend-compatible default behaviour)."""
    redacted, _ = redact_value_with_count(value, max_chars, hostname, hint, username)
    return redacted


def redact_data(
    data: Any,
    hostname: str = "",
    hint: str | None = None,
    username: str | None = None,
) -> tuple[Any, int]:
    """Recursively redact a JSON-like payload.

    Dict keys named like command lines are dropped to
    ``[cmdline dropped]`` (counted); every string value is redacted;
    numbers/bools/None pass through unchanged.
    """
    user = _os_username() if username is None else (username or "")

    def _walk(node: Any) -> tuple[Any, int]:
        if isinstance(node, dict):
            total = 0
            out: dict[Any, Any] = {}
            for key, val in node.items():
                if isinstance(key, str) and key.strip().lower() in CMDLINE_KEYS:
                    out[key] = "[cmdline dropped]"
                    total += 1
                    continue
                red, n = _walk(val)
                out[key] = red
                total += n
            return out, total
        if isinstance(node, list):
            total = 0
            items: list[Any] = []
            for entry in node:
                red, n = _walk(entry)
                items.append(red)
                total += n
            return items, total
        if isinstance(node, tuple):
            red_list, n = _walk(list(node))
            return tuple(red_list), n
        if isinstance(node, str):
            redacted, n = _subn_all(node, hostname, hint, user)
            return redacted, n
        return node, 0

    return _walk(data)
