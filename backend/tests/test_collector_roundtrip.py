"""Collector roundtrip: collect -> chunk -> manifest -> ZIP -> verify.

Covers the D3a chunked-doc case, the committed samples, consent gates,
tool-arg compatibility with the backend registry, and the guarantee that
no raw hostname/secret leaves the package.
"""

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector import __main__ as collector_cli
from collector import archive, chunker, hashverify, manifest
from collector.collect_windows import (
    CATEGORIES,
    FIXTURE_HOSTNAME,
    FIXTURE_USERNAME,
    collect_all,
    format_consent_screen,
)
from collector.redact_import import hash_hostname, redact_data

SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "collector",
    "samples",
)
FIXTURE_HINT = "roundtrip-pc"


def _collect(**overrides):
    params = {
        "consent_ack": True,
        "fixture": True,
        "hostname": FIXTURE_HOSTNAME,
        "target_hint": FIXTURE_HINT,
        "username": FIXTURE_USERNAME,
        "service_name": "wuauserv",
    }
    params.update(overrides)
    return collect_all(**params)


def _package(result, tmp_path, name="pkg.zip", payloads=None):
    payloads = payloads or {"notes/note.txt": b"roundtrip note\n"}
    chunked, chunk_warnings = chunker.chunk_entries(result.entries)
    finalized = manifest.finalize_entries(chunked)
    mani = manifest.build_manifest(
        hostname_hash=result.hostname_hash,
        os_info=result.os_info,
        evidence=finalized,
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()},
        target_hint=result.target_hint,
        duration_ms=result.duration_ms,
        warnings=[*result.warnings, *chunk_warnings],
    )
    dest = tmp_path / name
    archive.create_package(mani, payloads, dest)
    return dest, mani


def _extracted_text(root):
    texts = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            texts.append(path.read_bytes().decode("utf-8", errors="replace"))
    return "\n".join(texts)


def test_collect_fixture_roundtrip(tmp_path):
    result = _collect()
    assert len(result.entries) == 10
    assert result.hostname_hash == hash_hostname(FIXTURE_HOSTNAME)
    assert result.target_hint == FIXTURE_HINT
    dest, mani = _package(result, tmp_path)
    out, loaded, _ = archive.extract_and_verify(dest, tmp_path / "out")
    assert loaded["package_id"] == mani["package_id"]
    assert len(loaded["evidence"]) == len(mani["evidence"])
    assert hashverify.verify_package_dir(out, loaded) == []
    # Consent receipt covers every category with privilege flags.
    assert {r["category"] for r in result.consent_receipt} == set(CATEGORIES)
    assert all(r["privilege"] for r in result.consent_receipt)


def test_collect_requires_consent():
    with pytest.raises(PermissionError):
        collect_all(fixture=True)
    screen = format_consent_screen()
    for key in CATEGORIES:
        assert CATEGORIES[key]["label"] in screen


def test_collect_rejects_unknown_category_and_leaky_hint():
    with pytest.raises(ValueError, match="[Cc]ategor"):
        collect_all(categories=["nope"], consent_ack=True, fixture=True)
    with pytest.raises(ValueError, match="[Hh]ostname"):
        _collect(target_hint=FIXTURE_HOSTNAME)


def test_chunked_doc_reassembles(tmp_path):
    result = _collect()
    big_text = "line %d: ContosoVPN tunnel failed, code 0xc0000005\n" * 600
    raw = {"doc_id": "d1", "log_text": big_text}
    redacted, count = redact_data(raw, FIXTURE_HOSTNAME, FIXTURE_HINT, FIXTURE_USERNAME)
    redacted["provenance"] = {"redaction_count": count}
    assert chunker.needs_chunking(redacted)
    raw_entry = {
        "id": "c-doc", "category": "app_crashes", "source_suffix": "fixture",
        "collected_at": "2026-10-28T17:00:00Z", "data": redacted,
        "sha256": "pending", "size": 0,
    }
    chunks = chunker.chunk_entry(raw_entry)
    assert len(chunks) >= 2
    assert chunker.validate_chunk_chain(chunks) == []
    assert chunker.unchunk_data(chunks) == redacted
    for chunk in chunks:
        assert chunker.data_size_bytes(chunk["data"]) <= chunker.MAX_DATA_BYTES
    chunked, _ = chunker.chunk_entries([*result.entries, raw_entry])
    finalized = manifest.finalize_entries(chunked)
    mani = manifest.build_manifest(
        hostname_hash=result.hostname_hash,
        os_info=result.os_info,
        evidence=finalized,
        file_hashes={},
    )
    errors, _ = manifest.validate_manifest(mani)
    assert errors == []


def test_committed_samples_verify():
    basic = os.path.join(SAMPLES_DIR, "sample_basic.zip")
    chunked_pkg = os.path.join(SAMPLES_DIR, "sample_chunked.zip")
    assert os.path.isfile(basic) and os.path.isfile(chunked_pkg)
    import tempfile

    for path in (basic, chunked_pkg):
        tmp = tempfile.mkdtemp(prefix="fieldrook-roundtrip-")
        try:
            out, loaded, _ = archive.extract_and_verify(path, os.path.join(tmp, "pkg"))
            errors, _ = manifest.validate_manifest(loaded)
            assert errors == []
            assert hashverify.verify_package_dir(out, loaded) == []
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)


def test_basic_sample_has_no_chunks_chunked_sample_reassembles():
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="fieldrook-samples-")
    try:
        _, basic, _ = archive.extract_and_verify(
            os.path.join(SAMPLES_DIR, "sample_basic.zip"), os.path.join(tmp, "basic")
        )
        _, chunked_pkg, _ = archive.extract_and_verify(
            os.path.join(SAMPLES_DIR, "sample_chunked.zip"), os.path.join(tmp, "chunked")
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert all("chunk_seq" not in e["data"] for e in basic["evidence"])
    chunks = [e for e in chunked_pkg["evidence"] if "chunk_seq" in e["data"]]
    assert len(chunks) >= 2
    assert chunker.validate_chunk_chain(chunks) == []
    doc = chunker.unchunk_data(chunks)
    assert "ContosoVPN" in doc["log_text"]
    seqs = sorted(c["data"]["chunk_seq"] for c in chunks)
    assert seqs == list(range(1, len(chunks) + 1))


def test_no_raw_secrets_or_hostname_in_package(tmp_path):
    result = _collect()
    dest, _ = _package(result, tmp_path)
    out, loaded, _ = archive.extract_and_verify(dest, tmp_path / "out")
    blob = _extracted_text(out)
    assert FIXTURE_HOSTNAME not in blob
    assert FIXTURE_HOSTNAME.lower() not in blob
    assert "abc123secret" not in blob
    assert "hunter2" not in blob
    assert "ops@example.com" not in blob
    assert "fieldtech@example.com" not in blob
    assert FIXTURE_USERNAME not in blob
    assert "[secret redacted]" in blob  # redaction markers survive
    assert loaded["hostname_hash"] == hash_hostname(FIXTURE_HOSTNAME)


def test_provenance_redaction_counts(tmp_path):
    result = _collect()
    counts = [
        e["data"].get("provenance", {}).get("redaction_count", 0)
        for e in result.entries
    ]
    assert all(isinstance(c, int) for c in counts)
    assert sum(counts) > 0  # fixture tasks/events carry redactable values


def test_tool_refs_validate_against_backend_registry():
    from app.tools.registry import REGISTRY, prepare_call

    result = _collect()
    assert result.entries
    for entry in result.entries:
        tool = entry.get("tool_name")
        if tool is None:
            assert entry.get("tool_args") is None
            continue
        assert tool in REGISTRY
        _, parsed = prepare_call(tool, entry.get("tool_args") or {})
        assert parsed is not None


def test_cli_collect_and_validate(tmp_path):
    dest = tmp_path / "cli.zip"
    code = collector_cli.main(
        ["collect", "--out", str(dest), "--yes", "--fixture", "--hint", "cli-pc"]
    )
    assert code == 0
    assert dest.exists()
    assert collector_cli.main(["validate", str(dest)]) == 0


def test_cli_refuses_without_consent(tmp_path):
    code = collector_cli.main(
        ["collect", "--out", str(tmp_path / "no.zip"), "--fixture"]
    )
    assert code == 2
    assert not (tmp_path / "no.zip").exists()


def test_manifest_json_is_deterministic_shape(tmp_path):
    result = _collect()
    _, mani = _package(result, tmp_path)
    assert mani["schema_version"] == "1.0"
    assert mani["collector_lang"] == "python"
    assert set(mani) == {
        "schema_version", "package_id", "collector_version", "collector_lang",
        "created_at", "hostname_hash", "target_hint", "os", "duration_ms",
        "warnings", "evidence", "file_hashes",
    }
    assert json.loads(json.dumps(mani)) == mani

def test_oversize_live_entry_flows_through_chunk_finalize(tmp_path):
    """M024.1: Fury c-8 (>12KB live tasks) must chunk, not abort collection."""
    big = {"tasks": [{"name": f"task-{i:04d}", "detail": "x" * 200} for i in range(200)]}
    assert chunker.data_size_bytes(big) > chunker.MAX_DATA_BYTES
    raw_entry = {
        "id": "c-live",
        "category": "scheduled_tasks",
        "source_suffix": "live",
        "collected_at": manifest.utc_now_iso(),
        "data": big,
        "tool_name": "get_scheduled_tasks",
        "tool_args": {},
    }
    chunked, warnings = chunker.chunk_entries([raw_entry])
    assert len(chunked) > 1
    assert warnings and "pre-chunked" in warnings[0]
    finalized = manifest.finalize_entries(chunked)
    assert all("sha256" in e and "size" in e for e in finalized)
    mani = manifest.build_manifest(
        hostname_hash="dd" * 32,
        os_info={"platform": "win32", "version": "11", "build": "26100"},
        evidence=finalized,
    )
    errors, _ = manifest.validate_manifest(mani)
    assert errors == []
    assert chunker.unchunk_data(finalized) == big
