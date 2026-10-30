"""Single-sourced release version (M025 BETA).

Reads the ``VERSION`` file at the repo root (dev) or bundled beside the
frozen payload. Never raises: an unreadable version degrades to a clearly
labeled dev fallback instead of breaking startup or ``/api/status``.
"""

from __future__ import annotations

from .paths import version_file

FALLBACK_VERSION = "0.0.0-dev"


def get_version() -> str:
    """Release version string, e.g. ``0.4.0``."""
    try:
        text = version_file().read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK_VERSION
    first_line = text.splitlines()[0].strip() if text else ""
    return first_line or FALLBACK_VERSION
