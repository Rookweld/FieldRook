"""Build + validate ``forge.collector-manifest/v1`` (contracts v1, 1B).

Manifest (``manifest.json`` at ZIP root, required)::

    schema_version: "1.0"   (reject unknown major, warn on minor)
    package_id: uuid4
    collector_version: "x.y.z"
    collector_lang: "python" | "dotnet"
    created_at: UTC ISO-8601
    hostname_hash: sha256 hex
    target_hint: str | None
    os: {platform, version, build}
    duration_ms: int
    warnings: [str]
    evidence: [manifest entries]
    file_hashes: {relative_path: sha256}

Entry::

    {id, category, source_suffix, tool_name?, tool_args?, collected_at,
     data (object, <=12KB or pre-chunked per D3a), error?, sha256, size,
     refresh_of?}

Contract notes:

- ``category`` is free-form; unknown categories ingest with a warning and
  are never rejected. :data:`KNOWN_CATEGORIES` is the registry-bound set
  (lead-verified at contracts base) used only to decide the warning.
- ``tool_name`` must be in :data:`TOOL_NAMES` (the 14 lead-verified
  registry tools) or null; anything else is an error. ``tool_args`` must
  be an object or null; full ``prepare_call`` validation runs at lead
  import (the portable collector is stdlib-only and carries no pydantic
  models), so structural checks here are intentionally shallow.
- ``data`` canonical size/hash use the shared algorithm (see
  ``hashverify.py`` / ``chunker.py``); entries whose data exceeds 12KB
  without ``chunk_seq``/``chunk_of`` are rejected (D3a).
- Chunks carry ``chunk_seq``/``chunk_of`` inside ``data`` with a
  ``refresh_of`` chain; validated structurally (see ``chunker.py``).

Stdlib only. No imports from this package (size/hash helpers are local
copies of the shared 3-line algorithm so each module stays
single-file-friendly).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "SCHEMA_MINOR",
    "COLLECTOR_VERSION",
    "MANIFEST_NAME",
    "MAX_DATA_BYTES",
    "TOOL_NAMES",
    "KNOWN_CATEGORIES",
    "canonical_bytes",
    "data_size_bytes",
    "entry_hash",
    "utc_now_iso",
    "parse_utc_iso",
    "new_package_id",
    "build_entry",
    "build_manifest",
    "validate_manifest",
    "manifest_sha256",
]

SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = 1
SCHEMA_MINOR = 0
COLLECTOR_VERSION = "1.0.0"
MANIFEST_NAME = "manifest.json"
MAX_DATA_BYTES = 12 * 1024

# Lead-verified at contracts base (FORGE_CONTRACTS.md verification note):
# the 14 registered tools. Frozen here so the portable collector can
# validate tool_name without importing the backend registry.
TOOL_NAMES = frozenset(
    {
        "list_services",
        "get_service_details",
        "search_event_logs",
        "get_os_info",
        "get_network_adapters",
        "get_ip_config",
        "get_dns_config",
        "get_connections",
        "get_demo_worker_health",
        "interpret_error_code",
        "search_application_crashes",
        "get_process_info",
        "test_dns_resolution",
        "get_scheduled_tasks",
    }
)

# Registry-bound categories (registry.py ToolSpec.category values) plus the
# legacy collector categories (service_status, startup_type). Unknown
# categories warn, never reject.
KNOWN_CATEGORIES = frozenset(
    {
        "service_list",
        "service_details",
        "service_status",
        "startup_type",
        "event_log",
        "os_info",
        "net_adapters",
        "ip_config",
        "dns_config",
        "connections",
        "demo_worker",
        "error_code",
        "app_crashes",
        "process_info",
        "dns_test",
        "scheduled_tasks",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SCHEMA_RE = re.compile(r"^(\d+)\.(\d+)$")


def canonical_bytes(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def data_size_bytes(data: Any) -> int:
    return len(canonical_bytes(data))


def entry_hash(data: Any) -> tuple[str, int]:
    blob = canonical_bytes(data)
    return hashlib.sha256(blob).hexdigest(), len(blob)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc_iso(value: object) -> datetime | None:
    """Parse a UTC ISO-8601 timestamp; None when invalid or non-UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    try:
        utc = moment.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None
    # Must have been UTC already (no silent conversion of other zones).
    if moment.utcoffset() is None:
        return None
    if int(moment.utcoffset().total_seconds()) != 0:
        return None
    return utc


def new_package_id() -> str:
    return str(uuid.uuid4())


def _is_uuid4(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def build_entry(
    entry_id: str,
    category: str,
    data: dict[str, Any],
    source_suffix: str = "live",
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    collected_at: str | None = None,
    error: str | None = None,
    refresh_of: str | None = None,
) -> dict[str, Any]:
    """Build a manifest entry with computed ``sha256``/``size``.

    Raises :class:`ValueError` when ``data`` exceeds 12KB without chunk
    markers (callers must pre-chunk via ``chunker.py`` first).
    """
    if not isinstance(data, dict):
        raise ValueError("entry data must be an object.")
    if data_size_bytes(data) > MAX_DATA_BYTES and "chunk_seq" not in data:
        raise ValueError(
            f"entry {entry_id!r} data exceeds 12KB; pre-chunk it (D3a)."
        )
    sha256, size = entry_hash(data)
    entry: dict[str, Any] = {
        "id": entry_id,
        "category": category,
        "source_suffix": source_suffix,
        "collected_at": collected_at or utc_now_iso(),
        "data": data,
        "sha256": sha256,
        "size": size,
    }
    if tool_name is not None:
        entry["tool_name"] = tool_name
    if tool_args is not None:
        entry["tool_args"] = tool_args
    if error is not None:
        entry["error"] = error
    if refresh_of is not None:
        entry["refresh_of"] = refresh_of
    return entry


def build_manifest(
    hostname_hash: str,
    os_info: dict[str, str],
    evidence: list[dict[str, Any]],
    file_hashes: dict[str, str] | None = None,
    package_id: str | None = None,
    collector_version: str = COLLECTOR_VERSION,
    collector_lang: str = "python",
    target_hint: str | None = None,
    duration_ms: int = 0,
    warnings: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Assemble a manifest dict (validate with :func:`validate_manifest`)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": package_id or new_package_id(),
        "collector_version": collector_version,
        "collector_lang": collector_lang,
        "created_at": created_at or utc_now_iso(),
        "hostname_hash": hostname_hash,
        "target_hint": target_hint,
        "os": dict(os_info),
        "duration_ms": duration_ms,
        "warnings": list(warnings or []),
        "evidence": list(evidence),
        "file_hashes": dict(file_hashes or {}),
    }


def manifest_sha256(manifest: dict[str, Any]) -> str:
    """Canonical hash of a manifest dict (for ``data.provenance``)."""
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def _is_safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value or len(value) > 255:
        return False
    if "\x00" in value:
        return False
    text = value.replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return False
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return False
    return "/".join(parts) == text.strip("/")


def _validate_entry(
    entry: Any, index: int, ids_seen: set[str]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    where = f"evidence[{index}]"
    if isinstance(entry, dict) and isinstance(entry.get("id"), str):
        where = f"evidence[{entry['id']!r}]"
    if not isinstance(entry, dict):
        return [f"{where} must be an object."], []
    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not entry_id.strip() or len(entry_id) > 128:
        errors.append(f"{where} has a bad id (1..128 chars required).")
    elif entry_id in ids_seen:
        errors.append(f"duplicate evidence id {entry_id!r}.")
    else:
        ids_seen.add(entry_id)
    category = entry.get("category")
    if not isinstance(category, str) or not category.strip():
        errors.append(f"{where} has a bad category (non-empty string required).")
    elif category not in KNOWN_CATEGORIES:
        warnings.append(
            f"{where} has unknown category {category!r}; ingests with warning."
        )
    suffix = entry.get("source_suffix")
    if (
        not isinstance(suffix, str)
        or not suffix.strip()
        or len(suffix) > 64
        or any(ch.isspace() for ch in suffix)
        or ":" in suffix
    ):
        errors.append(
            f"{where} has a bad source_suffix (1..64 chars, no whitespace/colon)."
        )
    tool_name = entry.get("tool_name")
    if tool_name is not None and tool_name not in TOOL_NAMES:
        errors.append(f"{where} has unknown tool_name {tool_name!r} (must be in REGISTRY or null).")
    tool_args = entry.get("tool_args")
    if tool_args is not None:
        if not isinstance(tool_args, dict):
            errors.append(f"{where} tool_args must be an object or null.")
        elif tool_name is None:
            errors.append(f"{where} has tool_args without tool_name.")
    if parse_utc_iso(entry.get("collected_at")) is None:
        errors.append(f"{where} has a bad collected_at (UTC ISO-8601 required).")
    data = entry.get("data")
    if not isinstance(data, dict):
        errors.append(f"{where} data must be an object.")
    else:
        size = data_size_bytes(data)
        is_chunk = "chunk_seq" in data or "chunk_of" in data
        if size > MAX_DATA_BYTES and not is_chunk:
            errors.append(
                f"{where} data is {size} bytes (>12KB) and not pre-chunked (D3a)."
            )
        if is_chunk:
            seq, total = data.get("chunk_seq"), data.get("chunk_of")
            if (
                not isinstance(seq, int)
                or isinstance(seq, bool)
                or not isinstance(total, int)
                or isinstance(total, bool)
                or total < 2
                or not 1 <= seq <= total
            ):
                errors.append(f"{where} has invalid chunk_seq/chunk_of.")
        expected_hash, expected_size = entry_hash(data)
        if entry.get("sha256") != expected_hash:
            errors.append(f"{where} sha256 mismatch (expected {expected_hash}).")
        if entry.get("size") != expected_size:
            errors.append(f"{where} size mismatch (expected {expected_size}).")
    error = entry.get("error")
    if error is not None and not isinstance(error, str):
        errors.append(f"{where} error must be a string or null.")
    refresh_of = entry.get("refresh_of")
    if refresh_of is not None and (
        not isinstance(refresh_of, str) or not refresh_of.strip()
    ):
        errors.append(f"{where} refresh_of must be an evidence id or null.")
    return errors, warnings


def validate_manifest(manifest: Any) -> tuple[list[str], list[str]]:
    """Validate a manifest; returns ``(errors, warnings)``.

    Any error means the whole package must be rejected (lead maps these
    to HTTP 422 detail entries). Warnings ingest with a warning.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object."], []
    schema = manifest.get("schema_version")
    match = _SCHEMA_RE.match(schema) if isinstance(schema, str) else None
    if not match:
        errors.append("schema_version must look like 'M.m' (e.g. '1.0').")
    else:
        major, minor = int(match.group(1)), int(match.group(2))
        if major != SCHEMA_MAJOR:
            errors.append(
                f"unsupported schema_version major {major} (want {SCHEMA_MAJOR})."
            )
        elif minor != SCHEMA_MINOR:
            warnings.append(
                f"schema_version minor {minor} differs from {SCHEMA_MINOR}; ingesting with warning."
            )
    if not _is_uuid4(manifest.get("package_id")):
        errors.append("package_id must be a uuid4 string.")
    version = manifest.get("collector_version")
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        errors.append("collector_version must look like 'x.y.z'.")
    if manifest.get("collector_lang") not in ("python", "dotnet"):
        errors.append("collector_lang must be 'python' or 'dotnet'.")
    if parse_utc_iso(manifest.get("created_at")) is None:
        errors.append("created_at must be UTC ISO-8601.")
    if not isinstance(manifest.get("hostname_hash"), str) or not _SHA256_RE.match(
        manifest.get("hostname_hash", "")
    ):
        errors.append("hostname_hash must be a sha256 hex digest.")
    hint = manifest.get("target_hint")
    if hint is not None and not isinstance(hint, str):
        errors.append("target_hint must be a string or null.")
    elif isinstance(hint, str) and (not hint.strip() or len(hint) > 128):
        # Contract says str|None with no bound: empty/overlong hints ingest
        # with a warning, never rejected (mirrors unknown-category leniency).
        warnings.append("target_hint is empty or over 128 chars; ingesting with warning.")
    os_info = manifest.get("os")
    if not isinstance(os_info, dict):
        errors.append("os must be an object {platform, version, build}.")
    else:
        for key in ("platform", "version", "build"):
            if not isinstance(os_info.get(key), str):
                errors.append(f"os.{key} must be a string.")
    duration = manifest.get("duration_ms")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
        errors.append("duration_ms must be an int >= 0.")
    manifest_warnings = manifest.get("warnings")
    if not isinstance(manifest_warnings, list) or not all(
        isinstance(w, str) for w in manifest_warnings
    ):
        errors.append("warnings must be a list of strings.")
    evidence = manifest.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be a list.")
        evidence = []
    ids_seen: set[str] = set()
    for index, entry in enumerate(evidence):
        entry_errors, entry_warnings = _validate_entry(entry, index, ids_seen)
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)
    # refresh_of targets must exist in-package.
    for entry in evidence:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("refresh_of")
        if isinstance(ref, str) and ref and ref not in ids_seen:
            errors.append(
                f"evidence[{entry.get('id')!r}] refresh_of={ref!r} is dangling."
            )
    file_hashes = manifest.get("file_hashes")
    if not isinstance(file_hashes, dict):
        errors.append("file_hashes must be an object {relative_path: sha256}.")
    else:
        for rel, digest in file_hashes.items():
            if not _is_safe_relative_path(rel):
                errors.append(f"file_hashes key is not a safe relative path: {rel!r}.")
            if not isinstance(digest, str) or not _SHA256_RE.match(digest):
                errors.append(f"file_hashes[{rel!r}] is not a sha256 hex digest.")
    return errors, warnings
