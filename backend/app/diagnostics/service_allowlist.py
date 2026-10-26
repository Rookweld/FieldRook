"""Validated service identifiers.

Only names matching `_SERVICE_NAME_RE` are ever interpolated into the
allowlisted PowerShell command templates. The pattern excludes whitespace,
quotes, and shell metacharacters, so a validated name cannot break out of the
single-quoted argument in those fixed templates.
"""

from __future__ import annotations

import re

_SERVICE_NAME_RE = re.compile(r"[A-Za-z0-9_.\-]{1,64}")


class InvalidServiceNameError(ValueError):
    """Raised when a service identifier fails validation."""


def validate_service_name(name: object) -> str:
    if not isinstance(name, str):
        raise InvalidServiceNameError("Service name must be a string.")
    cleaned = name.strip()
    if not _SERVICE_NAME_RE.fullmatch(cleaned):
        raise InvalidServiceNameError(
            f"Invalid service name {name!r}: use 1-64 characters of A-Z a-z 0-9 _ . -"
        )
    return cleaned
