"""Pre-ingest hash verification for collector packages (contracts v1, section 2).

Atomicity rule: any ``file_hashes`` mismatch — or any entry ``sha256`` /
``size`` mismatch — rejects the WHOLE package. No partial ingest.

Canonical JSON (shared algorithm with ``chunker.py`` and ``manifest.py``;
kept dependency-free so each module stays single-file-friendly)::

    json.dumps(data, sort_keys=True, separators=(",", ":"),
               ensure_ascii=False, default=str).encode("utf-8")

Stdlib only. No imports from this package.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "SHA256_RE",
    "READ_CHUNK_BYTES",
    "hash_bytes",
    "hash_file",
    "canonical_bytes",
    "data_size_bytes",
    "entry_hash",
    "verify_file_hashes",
    "verify_entry_hashes",
    "verify_package_dir",
]

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
READ_CHUNK_BYTES = 65536


def hash_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def hash_file(path: str | Path, chunk_size: int = READ_CHUNK_BYTES) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def data_size_bytes(data: Any) -> int:
    return len(canonical_bytes(data))


def entry_hash(data: Any) -> tuple[str, int]:
    blob = canonical_bytes(data)
    return hashlib.sha256(blob).hexdigest(), len(blob)


def _is_safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value or len(value) > 255:
        return False
    if "\x00" in value:
        return False
    text = value.replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return False
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if not parts:
        return False
    if any(p == ".." for p in parts):
        return False
    return "/".join(parts) == text.strip("/")


def verify_file_hashes(root: str | Path, file_hashes: dict[str, str]) -> list[str]:
    """Verify every ``file_hashes`` entry against files under ``root``.

    Errors cover: missing files, hash mismatches, malformed hashes,
    unsafe paths, and unlisted extra files (anything under ``root``
    except ``manifest.json`` must appear in ``file_hashes``).
    """
    errors: list[str] = []
    root_path = Path(root)
    if not isinstance(file_hashes, dict):
        return ["file_hashes must be an object."]
    for rel, expected in file_hashes.items():
        if not _is_safe_relative_path(rel):
            errors.append(f"file_hashes key is not a safe relative path: {rel!r}.")
            continue
        if not isinstance(expected, str) or not SHA256_RE.match(expected):
            errors.append(f"file_hashes[{rel!r}] is not a sha256 hex digest.")
            continue
        target = root_path / rel.replace("\\", "/")
        try:
            resolved = target.resolve()
            root_resolved = root_path.resolve()
        except OSError:
            errors.append(f"payload file is missing: {rel!r}.")
            continue
        if root_resolved not in resolved.parents and resolved != root_resolved:
            errors.append(f"payload path escapes package root: {rel!r}.")
            continue
        if not resolved.is_file():
            errors.append(f"payload file is missing: {rel!r}.")
            continue
        try:
            actual = hash_file(resolved)
        except OSError as exc:
            errors.append(f"payload file is unreadable {rel!r}: {exc}.")
            continue
        if actual != expected:
            errors.append(
                f"hash mismatch for {rel!r}: expected {expected}, got {actual}."
            )
    # Unlisted extras (manifest.json itself is exempt: it carries file_hashes).
    try:
        for found in sorted(root_path.rglob("*")):
            if found.is_dir():
                continue
            rel = found.relative_to(root_path).as_posix()
            if rel == "manifest.json":
                continue
            if rel not in file_hashes:
                errors.append(f"unlisted payload file (not in file_hashes): {rel!r}.")
    except OSError as exc:
        errors.append(f"could not enumerate package directory: {exc}.")
    return errors


def verify_entry_hashes(evidence: list[dict[str, Any]]) -> list[str]:
    """Recompute each entry's ``sha256``/``size`` over canonical data JSON."""
    errors: list[str] = []
    if not isinstance(evidence, list):
        return ["evidence must be a list."]
    for index, entry in enumerate(evidence):
        where = f"evidence[{index}]"
        if isinstance(entry, dict) and entry.get("id") is not None:
            where = f"evidence[{entry.get('id')!r}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be an object.")
            continue
        if "data" not in entry or not isinstance(entry["data"], dict):
            errors.append(f"{where} has no data object to hash.")
            continue
        expected_hash, expected_size = entry_hash(entry["data"])
        if entry.get("sha256") != expected_hash:
            errors.append(
                f"{where} sha256 mismatch: expected {expected_hash}, "
                f"got {entry.get('sha256')!r}."
            )
        if entry.get("size") != expected_size:
            errors.append(
                f"{where} size mismatch: expected {expected_size}, "
                f"got {entry.get('size')!r}."
            )
    return errors


def verify_package_dir(root: str | Path, manifest: dict[str, Any]) -> list[str]:
    """Full pre-ingest hash gate: file hashes + entry hashes.

    Returns a (possibly empty) machine-readable error list. Any non-empty
    result means the whole package must be rejected.
    """
    if not isinstance(manifest, dict):
        return ["manifest must be an object."]
    errors = verify_file_hashes(root, manifest.get("file_hashes", {}))
    errors.extend(verify_entry_hashes(manifest.get("evidence", [])))
    return errors
