"""ZIP package create + safe-extract (contracts v1, section 2).

- ZIP only (stdlib ``zipfile``, Windows-native). No tar.
- Reject: symlinks / hardlinks / dev nodes (``external_attr``), absolute
  paths, ``..`` after normpath, non-UTF-8 or >255-char names, drive
  prefixes. Root ``manifest.json`` required.
- Payload suffixes ``.json`` / ``.txt`` / ``.md`` / ``.log`` only.
  Images are metadata-only entries, never bytes in v1.
- Caps: 2MB/file, 20MB total, 200 files, 50x compression-ratio guard
  with streaming abort + temp cleanup.
- ``file_hashes`` verification itself lives in ``hashverify.py`` (called
  by the lead import path and by :func:`extract_and_verify` here via a
  local import so this module stays single-file-friendly for creation).

Stdlib only. No package-level imports.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "ArchiveError",
    "MANIFEST_NAME",
    "ALLOWED_SUFFIXES",
    "MAX_FILE_BYTES",
    "MAX_TOTAL_BYTES",
    "MAX_FILES",
    "MAX_RATIO",
    "READ_CHUNK_BYTES",
    "validate_member_name",
    "create_package",
    "safe_extract",
    "extract_and_verify",
    "read_manifest_from_zip",
]

MANIFEST_NAME = "manifest.json"
ALLOWED_SUFFIXES = frozenset({".json", ".txt", ".md", ".log"})
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_FILES = 200
MAX_RATIO = 50
READ_CHUNK_BYTES = 65536


class ArchiveError(ValueError):
    """A package violates the archive contract (lead maps to HTTP 422)."""


def _is_unsafe_mode(external_attr: int) -> str | None:
    unix_mode = (external_attr >> 16) & 0o170000
    if unix_mode == 0:
        return None  # Windows/DOS-created entry: no unix type bits.
    if unix_mode == stat.S_IFLNK:
        return "symlink"
    if unix_mode in (stat.S_IFCHR, stat.S_IFBLK):
        return "device node"
    if unix_mode == stat.S_IFIFO:
        return "fifo"
    if unix_mode == stat.S_IFSOCK:
        return "socket"
    if unix_mode not in (stat.S_IFREG, stat.S_IFDIR):
        return f"special file (mode {oct(unix_mode)})"
    return None


def validate_member_name(name: str) -> None:
    """Raise :class:`ArchiveError` when a ZIP member name is unsafe."""
    if not isinstance(name, str) or not name:
        raise ArchiveError("ZIP member has an empty name.")
    try:
        name.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ArchiveError(f"ZIP member name is not valid UTF-8: {name!r}.")
    if "\x00" in name:
        raise ArchiveError(f"ZIP member name contains NUL: {name!r}.")
    if len(name) > 255:
        raise ArchiveError(f"ZIP member name exceeds 255 chars: {name!r}.")
    text = name.replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ArchiveError(f"ZIP member is absolute or has a drive prefix: {name!r}.")
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if not parts:
        raise ArchiveError(f"ZIP member name is empty after normalization: {name!r}.")
    if any(p == ".." for p in parts):
        raise ArchiveError(f"ZIP member escapes the package root: {name!r}.")


def _check_entry_type(info: zipfile.ZipInfo) -> None:
    bad = _is_unsafe_mode(info.external_attr)
    if bad:
        raise ArchiveError(f"ZIP member {info.filename!r} is a {bad}; rejected.")


def create_package(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, bytes] | None,
    dest: str | Path,
) -> Path:
    """Write a contract-valid package ZIP.

    ``manifest`` must already carry correct ``file_hashes`` for
    ``payloads`` (keys are safe relative paths, values are bytes).
    Raises :class:`ArchiveError` on any contract violation; no partial
    file is left behind.
    """
    dest_path = Path(dest)
    files = dict(payloads or {})
    if not isinstance(manifest, Mapping):
        raise ArchiveError("manifest must be an object.")
    file_hashes = manifest.get("file_hashes", {})
    if not isinstance(file_hashes, Mapping):
        raise ArchiveError("manifest file_hashes must be an object.")
    if set(files) != set(file_hashes):
        missing = sorted(set(file_hashes) - set(files))
        extra = sorted(set(files) - set(file_hashes))
        raise ArchiveError(
            f"payload/file_hashes mismatch (missing={missing}, extra={extra})."
        )
    for rel, blob in files.items():
        validate_member_name(rel)
        if not isinstance(blob, (bytes, bytearray)):
            raise ArchiveError(f"payload {rel!r} must be bytes.")
        suffix = Path(rel.replace("\\", "/")).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ArchiveError(
                f"payload {rel!r} has suffix {suffix!r}; "
                "only .json/.txt/.md/.log are allowed."
            )
        if len(blob) > MAX_FILE_BYTES:
            raise ArchiveError(f"payload {rel!r} exceeds the 2MB/file cap.")
        actual = hashlib.sha256(bytes(blob)).hexdigest()
        if actual != file_hashes[rel]:
            raise ArchiveError(f"payload {rel!r} does not match file_hashes.")
    total = sum(len(b) for b in files.values())
    manifest_blob = json.dumps(
        dict(manifest), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")
    if len(manifest_blob) > MAX_FILE_BYTES:
        raise ArchiveError("manifest.json exceeds the 2MB/file cap.")
    total += len(manifest_blob)
    if total > MAX_TOTAL_BYTES:
        raise ArchiveError("package exceeds the 20MB total cap.")
    if len(files) + 1 > MAX_FILES:
        raise ArchiveError("package exceeds the 200-file cap.")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_name(dest_path.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, manifest_blob)
            for rel in sorted(files):
                archive.writestr(rel, bytes(files[rel]))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    tmp_path.replace(dest_path)
    return dest_path


def read_manifest_from_zip(zip_path: str | Path) -> dict[str, Any]:
    """Read + JSON-parse the root ``manifest.json`` without extracting."""
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            try:
                blob = archive.read(MANIFEST_NAME)
            except KeyError:
                raise ArchiveError("package has no root manifest.json.")
            if len(blob) > MAX_FILE_BYTES:
                raise ArchiveError("manifest.json exceeds the 2MB/file cap.")
            try:
                manifest = json.loads(blob.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ArchiveError(f"manifest.json is not valid UTF-8 JSON: {exc}.")
            if not isinstance(manifest, dict):
                raise ArchiveError("manifest.json must be a JSON object.")
            return manifest
    except zipfile.BadZipFile as exc:
        raise ArchiveError(f"not a valid ZIP package: {exc}.")


def safe_extract(zip_path: str | Path, dest_dir: str | Path) -> Path:
    """Extract a package with full archive-gate validation (streaming).

    On any violation the destination is removed (temp cleanup) and
    :class:`ArchiveError` is raised. Returns the destination path.
    Hash and manifest-schema validation are the caller's next steps
    (see :func:`extract_and_verify`).
    """
    src = Path(zip_path)
    dest = Path(dest_dir)
    if dest.exists() and any(dest.iterdir()):
        raise ArchiveError(f"destination {str(dest)!r} is not empty.")
    dest.mkdir(parents=True, exist_ok=True)

    def _fail(message: str) -> ArchiveError:
        shutil.rmtree(dest, ignore_errors=True)
        return ArchiveError(message)

    try:
        with zipfile.ZipFile(src, "r") as archive:
            members = archive.infolist()
            files = [m for m in members if not m.is_dir()]
            if len(files) > MAX_FILES:
                raise _fail("package exceeds the 200-file cap.")
            names = [m.filename for m in files]
            if len(set(names)) != len(names):
                raise _fail("package contains duplicate member names.")
            if MANIFEST_NAME not in names:
                raise _fail("package has no root manifest.json.")
            declared_total = sum(m.file_size for m in files)
            if declared_total > MAX_TOTAL_BYTES:
                raise _fail("package exceeds the 20MB total cap.")
            written_total = 0
            for info in files:
                validate_member_name(info.filename)
                _check_entry_type(info)
                suffix = Path(info.filename.replace("\\", "/")).suffix.lower()
                if suffix not in ALLOWED_SUFFIXES:
                    raise _fail(
                        f"member {info.filename!r} has suffix {suffix!r}; "
                        "only .json/.txt/.md/.log are allowed."
                    )
                if info.file_size > MAX_FILE_BYTES:
                    raise _fail(
                        f"member {info.filename!r} exceeds the 2MB/file cap."
                    )
                if info.compress_size > 0 and info.file_size > info.compress_size * MAX_RATIO:
                    raise _fail(
                        f"member {info.filename!r} exceeds the 50x ratio guard "
                        f"({info.file_size} vs {info.compress_size} compressed)."
                    )
                target = dest / info.filename.replace("\\", "/")
                try:
                    resolved = target.resolve()
                    root_resolved = dest.resolve()
                except OSError:
                    raise _fail(f"member path is unresolvable: {info.filename!r}.")
                if root_resolved not in resolved.parents and resolved != root_resolved:
                    raise _fail(f"member escapes the package root: {info.filename!r}.")
                resolved.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info, "r") as reader, open(resolved, "wb") as writer:
                    while True:
                        chunk = reader.read(READ_CHUNK_BYTES)
                        if not chunk:
                            break
                        written += len(chunk)
                        written_total += len(chunk)
                        if written > MAX_FILE_BYTES:
                            raise _fail(
                                f"member {info.filename!r} exceeds the 2MB/file cap "
                                "(streaming abort)."
                            )
                        if written_total > MAX_TOTAL_BYTES:
                            raise _fail(
                                "package exceeds the 20MB total cap (streaming abort)."
                            )
                        writer.write(chunk)
                # Post-write ratio check on actual bytes (declared sizes
                # in hostile zips can lie; compress_size is authoritative).
                if info.compress_size > 0 and written > info.compress_size * MAX_RATIO:
                    raise _fail(
                        f"member {info.filename!r} exceeds the 50x ratio guard."
                    )
    except zipfile.BadZipFile as exc:
        raise _fail(f"not a valid ZIP package: {exc}.")
    except ArchiveError:
        # Direct raises (e.g. validate_member_name) bypass _fail: clean up here.
        shutil.rmtree(dest, ignore_errors=True)
        raise
    except OSError as exc:
        raise _fail(f"extraction I/O failed: {exc}.")
    return dest


def extract_and_verify(
    zip_path: str | Path, dest_dir: str | Path
) -> tuple[Path, dict[str, Any], list[str]]:
    """Extract + verify hashes + validate the manifest schema.

    Returns ``(dest, manifest, warnings)``. Raises :class:`ArchiveError`
    with machine-readable detail on any failure (destination cleaned).
    Local imports keep ``archive.py`` single-file-friendly.
    """
    from .hashverify import verify_package_dir  # noqa: PLC0415 - see docstring
    from .manifest import validate_manifest  # noqa: PLC0415 - see docstring

    dest = safe_extract(zip_path, dest_dir)
    try:
        manifest_path = dest / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise ArchiveError(f"manifest.json is unreadable: {exc}.")
    if not isinstance(manifest, dict):
        shutil.rmtree(dest, ignore_errors=True)
        raise ArchiveError("manifest.json must be a JSON object.")
    errors, warnings = validate_manifest(manifest)
    errors = list(errors)
    errors.extend(verify_package_dir(dest, manifest))
    if errors:
        shutil.rmtree(dest, ignore_errors=True)
        raise ArchiveError("package rejected: " + " | ".join(errors))
    return dest, manifest, warnings


def extract_to_temp(zip_path: str | Path) -> Path:
    """Extract a package to a fresh temp dir (caller must delete it)."""
    tmp = Path(tempfile.mkdtemp(prefix="fieldrook-collector-"))
    return safe_extract(zip_path, tmp / "package")
