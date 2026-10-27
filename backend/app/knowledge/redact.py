"""Redaction for the knowledge library.

Signatures store diagnostic shapes, not personal data: secret-like values,
email addresses, DOMAIN\\user forms, and the current OS username are masked
before anything is persisted. Command lines are never collected upstream
and never appear in signatures.
"""

from __future__ import annotations

import getpass
import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd|secret|token|apikey|api_key|clientsecret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)--?(password|passwd|pwd|secret|token|apikey|api_key)\s+\S+"),
)
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_USERID_PATTERN = re.compile(r"\b[A-Za-z0-9._-]{2,}\\[A-Za-z0-9._$-]{2,}\b")


def _os_username() -> str:
    try:
        return getpass.getuser().strip()
    except Exception:  # noqa: BLE001 - best effort
        return ""


def redact_text(text: str) -> str:
    cleaned = text or ""
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[secret redacted]", cleaned)
    cleaned = _EMAIL_PATTERN.sub("[email redacted]", cleaned)
    cleaned = _USERID_PATTERN.sub("[user redacted]", cleaned)
    username = _os_username()
    if username and len(username) >= 3:
        cleaned = re.sub(re.escape(username), "[user redacted]", cleaned, flags=re.IGNORECASE)
    return cleaned


def redact_value(value: object, max_chars: int = 200) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(redact_value(item, 60) for item in list(value)[:8]) + "]"
    text = redact_text(str(value)).strip().replace("\n", " ")
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return text
