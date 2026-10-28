"""Collector package import (FORGE lead wiring, contracts 1B/1C/1E/2).

POST /api/investigations/{id}/import-collector ingests a versioned
collector ZIP as untrusted data. Validation is atomic: every check runs
before any state mutation, and any failure rejects the whole package
with HTTP 422. No partial ingest, no code execution, no script runs.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import load_settings
from ..investigations.store import store
from ..schemas import (
    CollectorPackageRecord,
    InvestigationResponse,
    TargetIdentity,
    TargetOS,
)
from ..tools.registry import REGISTRY, ToolCallError, prepare_call

# The collector is a standalone stdlib package at the repo root (portable by
# design). Import it by path; the backend never depends on it at install time.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from collector import archive, chunker, hashverify  # noqa: E402
from collector import manifest as colmanifest  # noqa: E402
from collector import redact_import  # noqa: E402

router = APIRouter(tags=["collector"])

MAX_UPLOAD_BYTES = 21 * 1024 * 1024  # 20MB package cap + zip overhead slack
MAX_DATA_BYTES = 12 * 1024
ZIP_MAGIC = b"PK\x03\x04"


def _problem(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _read_upload_capped(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = upload.file.read(65536)
        if not piece:
            break
        total += len(piece)
        if total > MAX_UPLOAD_BYTES:
            raise _problem(413, f"Package exceeds the {MAX_UPLOAD_BYTES} byte upload cap.")
        chunks.append(piece)
    return b"".join(chunks)


def _validate_tool_ref(
    tool_name: object, tool_args: object, warnings: list[str], entry_id: str
) -> tuple[str | None, dict | None]:
    """Resolve a manifest tool reference to a validated (name, args) pair.

    Unknown names or invalid args degrade to None with a warning — the
    evidence still ingests, but it is not re-runnable.
    """
    if tool_name is None:
        return None, None
    if not isinstance(tool_name, str) or tool_name not in REGISTRY:
        warnings.append(f"entry {entry_id}: unknown tool_name {tool_name!r}; stored without rerun provenance")
        return None, None
    try:
        _, validated = prepare_call(tool_name, tool_args if tool_args is not None else {})
    except ToolCallError as exc:
        warnings.append(f"entry {entry_id}: tool_args rejected ({exc}); stored without rerun provenance")
        return None, None
    dumped = validated.model_dump(mode="json")
    return tool_name, dumped if isinstance(dumped, dict) else {}


@router.post(
    "/api/investigations/{investigation_id}/import-collector",
    response_model=InvestigationResponse,
)
async def import_collector(
    investigation_id: str,
    file: UploadFile | None = File(default=None),
    share_consent: bool = Form(default=False),
) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise _problem(404, f"Unknown investigation {investigation_id!r}.")
    if not share_consent:
        raise _problem(400, "Import requires explicit share_consent=true.")
    if file is None or not (file.filename or "").lower().endswith(".zip"):
        raise _problem(400, "A .zip collector package file is required.")
    payload = _read_upload_capped(file)
    if not payload.startswith(ZIP_MAGIC):
        raise _problem(422, "Upload is not a ZIP archive (bad magic).")

    tmpdir = Path(tempfile.mkdtemp(prefix="fieldrook-import-"))
    try:
        zip_path = tmpdir / "package.zip"
        zip_path.write_bytes(payload)
        try:
            raw_manifest = archive.read_manifest_from_zip(zip_path)
        except archive.ArchiveError as exc:
            raise _problem(422, f"Cannot read package manifest: {exc}") from exc
        errors, manifest_warnings = colmanifest.validate_manifest(raw_manifest)
        if errors:
            raise _problem(422, f"Invalid manifest: {'; '.join(errors[:8])}")
        try:
            extracted = archive.safe_extract(zip_path, tmpdir / "extracted")
        except archive.ArchiveError as exc:
            raise _problem(422, f"Unsafe archive rejected: {exc}") from exc
        problems = hashverify.verify_package_dir(extracted, raw_manifest)
        if problems:
            raise _problem(422, f"Package integrity failure: {'; '.join(problems[:8])}")
        entry_problems = hashverify.verify_entry_hashes(raw_manifest.get("evidence", []))
        if entry_problems:
            raise _problem(422, f"Evidence hash failure: {'; '.join(entry_problems[:8])}")
        chain_problems = chunker.validate_chunk_chain(raw_manifest.get("evidence", []))
        if chain_problems:
            raise _problem(422, f"Broken chunk chain: {'; '.join(chain_problems[:8])}")

        package_id = raw_manifest["package_id"]
        if any(p.package_id == package_id for p in state.collector_packages):
            raise _problem(409, f"Package {package_id} is already imported into this case.")
        try:
            manifest_digest = colmanifest.manifest_sha256(raw_manifest)
        except ValueError as exc:
            raise _problem(422, f"Cannot hash manifest: {exc}") from exc

        warnings: list[str] = [f"manifest: {w}" for w in manifest_warnings]
        entries: list[dict[str, Any]] = raw_manifest.get("evidence", [])
        prepared: list[dict[str, Any]] = []
        for entry in entries:
            entry_id = str(entry.get("id", "?"))
            data = entry.get("data")
            if not isinstance(data, dict):
                raise _problem(422, f"entry {entry_id}: data must be an object")
            if chunker.needs_chunking(data) and "chunk_seq" not in data:
                raise _problem(
                    422,
                    f"entry {entry_id}: data exceeds 12KB without chunk markers; "
                    "the collector must pre-chunk it (D3a)",
                )
            tool_name, tool_args = _validate_tool_ref(
                entry.get("tool_name"), entry.get("tool_args"), warnings, entry_id
            )
            redacted, redact_count = redact_import.redact_value_with_count(data)
            if not isinstance(redacted, dict):
                redacted = {"value": redacted}
            redacted.setdefault("provenance", {})
            if isinstance(redacted["provenance"], dict):
                redacted["provenance"]["collector"] = {
                    "package_id": package_id,
                    "collector_version": raw_manifest.get("collector_version", ""),
                    "manifest_sha256": manifest_digest,
                }
                redacted["provenance"]["collected_at"] = entry.get("collected_at")
                redacted["provenance"]["redaction_count"] = redact_count
            prepared.append({
                "local_id": entry_id,
                "category": str(entry.get("category", "collector")),
                "suffix": str(entry.get("source_suffix", "live")),
                "data": redacted,
                "error": entry.get("error"),
                "tool_name": tool_name,
                "tool_args": tool_args,
                "refresh_of": entry.get("refresh_of"),
                "chunk_seq": data.get("chunk_seq"),
            })

        # ---- ingest (all validation passed) ----
        local_to_ev: dict[str, str] = {}
        pending = sorted(prepared, key=lambda e: (e["chunk_seq"] is None, e["chunk_seq"] or 0))
        for item in pending:
            refresh_of = None
            if isinstance(item["refresh_of"], str) and item["refresh_of"] in local_to_ev:
                refresh_of = local_to_ev[item["refresh_of"]]
            created = state.add_evidence(
                category=item["category"],
                source=f"collector:{package_id}:{item['suffix']}",
                data=item["data"],
                error=item["error"] if isinstance(item["error"], str) else None,
                tool_name=item["tool_name"],
                tool_args=item["tool_args"],
                refresh_of=refresh_of,
            )
            local_to_ev[item["local_id"]] = created.id

        manifest_hash = str(raw_manifest.get("hostname_hash", ""))
        os_info = raw_manifest.get("os") or {}
        if state.target_identity is None:
            state.target_identity = TargetIdentity(
                hostname_hash=manifest_hash,
                hint=raw_manifest.get("target_hint"),
                os=TargetOS(
                    platform=str(os_info.get("platform", "")),
                    version=str(os_info.get("version", "")),
                    build=str(os_info.get("build", "")),
                ),
            )
        elif manifest_hash and state.target_identity.hostname_hash and (
            manifest_hash != state.target_identity.hostname_hash
        ):
            warnings.append(
                "package hostname_hash differs from this case's target identity; "
                "kept the case target and linked the package as imported evidence"
            )
        created_at: datetime | None = None
        try:
            created_at = datetime.fromisoformat(str(raw_manifest.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            created_at = None
        state.collector_packages.append(
            CollectorPackageRecord(
                package_id=package_id,
                collector_version=str(raw_manifest.get("collector_version", "")),
                collector_lang=str(raw_manifest.get("collector_lang", "")),
                created_at=created_at,
                hostname_hash=manifest_hash,
                manifest_sha256=manifest_digest,
                evidence_ids=[local_to_ev[i["local_id"]] for i in pending],
                warnings=list(raw_manifest.get("warnings", [])),
            )
        )
        state.add_activity(
            "collector_import",
            "Collector package imported",
            f"{package_id}: {len(pending)} items, {len(warnings)} import warnings",
            evidence_ids=[local_to_ev[i["local_id"]] for i in pending],
        )
        for warning in warnings:
            state.warnings.append(f"import {package_id}: {warning}")
        store.save(state)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)
