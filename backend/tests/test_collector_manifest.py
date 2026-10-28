"""Manifest build + validate (forge.collector-manifest/v1, contracts 1B)."""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector import chunker, manifest

HOST_HASH = "a" * 64
OS_INFO = {"platform": "Microsoft Windows 11 Pro", "version": "10.0.22631", "build": "22631"}
PACKAGE_ID = "11111111-1111-4111-8111-111111111111"


def _entry(**overrides):
    base = manifest.build_entry(
        entry_id="c-1",
        category="os_info",
        data={"caption": "Windows 11"},
        source_suffix="live",
        tool_name="get_os_info",
        tool_args={},
        collected_at="2026-10-28T17:00:00Z",
    )
    base.update(overrides)
    return base


def _manifest(**overrides):
    base = manifest.build_manifest(
        hostname_hash=HOST_HASH,
        os_info=dict(OS_INFO),
        evidence=[_entry()],
        file_hashes={},
        package_id=PACKAGE_ID,
        target_hint="front-desk-pc",
        duration_ms=123,
        warnings=[],
        created_at="2026-10-28T17:00:00Z",
    )
    base.update(overrides)
    return base


def _errors(**overrides):
    errors, _ = manifest.validate_manifest(_manifest(**overrides))
    return errors


def _warnings(**overrides):
    _, warnings = manifest.validate_manifest(_manifest(**overrides))
    return warnings


def test_valid_manifest_passes():
    errors, warnings = manifest.validate_manifest(_manifest())
    assert errors == []
    assert warnings == []


def test_build_entry_computes_hash_and_size():
    entry = _entry()
    expected_hash, expected_size = chunker.entry_hash({"caption": "Windows 11"})
    assert entry["sha256"] == expected_hash
    assert entry["size"] == expected_size


def test_build_entry_rejects_oversize_data():
    big = {"blob": "x" * (13 * 1024)}
    try:
        manifest.build_entry("c-9", "event_log", big)
    except ValueError as exc:
        assert "12KB" in str(exc)
    else:
        raise AssertionError("expected ValueError for oversize data")


def test_unknown_major_rejects():
    assert _errors(schema_version="2.0")


def test_minor_bump_warns_only():
    errors, warnings = manifest.validate_manifest(_manifest(schema_version="1.1"))
    assert errors == []
    assert len(warnings) == 1


def test_bad_schema_version_format():
    for bad in ("1", "v1", "1.0.0", "", None, 1.0):
        assert _errors(schema_version=bad), bad


def test_bad_package_id():
    for bad in ("not-a-uuid", "", None, "11111111-1111-1111-1111-111111111111"):
        assert _errors(package_id=bad), bad


def test_bad_collector_version():
    for bad in ("1.0", "v1.0.0", "1.0.0.0", "", None):
        assert _errors(collector_version=bad), bad


def test_bad_collector_lang():
    assert _errors(collector_lang="java")
    assert _errors(collector_lang=None)


def test_bad_created_at():
    for bad in ("2026-10-28", "tomorrow", "", None, "2026-10-28T17:00:00"):
        assert _errors(created_at=bad), bad
    # Non-UTC offsets are rejected (no silent conversion).
    assert _errors(created_at="2026-10-28T17:00:00+02:00")


def test_created_at_accepts_z_and_utc_offset():
    assert _errors(created_at="2026-10-28T17:00:00Z") == []
    assert _errors(created_at="2026-10-28T17:00:00+00:00") == []
    assert _errors(created_at="2026-10-28T17:00:00.123Z") == []


def test_bad_hostname_hash():
    for bad in ("xyz", "a" * 63, "A" * 64, "", None):
        assert _errors(hostname_hash=bad), bad


def test_target_hint_nullable_but_bounded():
    assert _errors(target_hint=None) == []
    assert _errors(target_hint=123) != []
    # Empty/overlong hints warn (contract: str|None), never reject.
    assert _errors(target_hint="") == []
    assert _warnings(target_hint="") != []
    assert _errors(target_hint="x" * 129) == []
    assert _warnings(target_hint="x" * 129) != []
    assert _errors(target_hint="ok-hint") == []


def test_bad_os_block():
    assert _errors(os={})
    assert _errors(os={"platform": "p", "version": 1, "build": "b"})
    assert _errors(os=None)
    assert _errors(os="windows")


def test_bad_duration():
    for bad in (-1, True, 1.5, "123", None):
        assert _errors(duration_ms=bad), bad


def test_bad_warnings():
    assert _errors(warnings="x")
    assert _errors(warnings=[1])
    assert _errors(warnings=None)


def test_manifest_must_be_object():
    errors, _ = manifest.validate_manifest([])
    assert errors


def test_duplicate_evidence_ids_rejected():
    other = _entry()
    other["id"] = "c-1"
    assert _errors(evidence=[_entry(), other])


def test_empty_category_rejected_unknown_warns():
    bad = _entry()
    bad["category"] = ""
    assert _errors(evidence=[bad])
    weird = _entry()
    weird["category"] = "future_category_x"
    errors, warnings = manifest.validate_manifest(_manifest(evidence=[weird]))
    assert errors == []
    assert len(warnings) == 1


def test_bad_source_suffix():
    for bad in ("", "has space", "has:colon", "x" * 65, None):
        entry = _entry()
        entry["source_suffix"] = bad
        assert _errors(evidence=[entry]), bad


def test_unknown_tool_name_rejected_null_ok():
    entry = _entry()
    entry["tool_name"] = "no_such_tool"
    assert _errors(evidence=[entry])
    entry = _entry()
    del entry["tool_name"]
    entry["tool_args"] = None
    assert _errors(evidence=[entry]) == []


def test_tool_args_requires_tool_and_object():
    entry = _entry()
    del entry["tool_name"]
    entry["tool_args"] = {"limit": 5}
    assert _errors(evidence=[entry])
    entry = _entry()
    entry["tool_args"] = [1]
    assert _errors(evidence=[entry])


def test_bad_collected_at():
    entry = _entry()
    entry["collected_at"] = "yesterday"
    assert _errors(evidence=[entry])


def test_data_must_be_object():
    entry = _entry()
    entry["data"] = [1, 2]
    assert _errors(evidence=[entry])


def test_oversize_unchunked_data_rejected():
    data = {"blob": "y" * (13 * 1024)}
    sha256, size = chunker.entry_hash(data)
    entry = {
        "id": "c-big", "category": "event_log", "source_suffix": "live",
        "collected_at": "2026-10-28T17:00:00Z", "data": data,
        "sha256": sha256, "size": size,
    }
    errors = _errors(evidence=[entry])
    assert any("12KB" in e for e in errors)


def test_entry_hash_and_size_mismatch():
    entry = _entry()
    entry["sha256"] = "b" * 64
    assert _errors(evidence=[entry])
    entry = _entry()
    entry["size"] += 1
    assert _errors(evidence=[entry])


def test_bad_chunk_markers_rejected():
    for seq, total in ((0, 3), (4, 3), (1, 1), ("1", 3), (1, "3")):
        data = {"chunk_seq": seq, "chunk_of": total, "chunk_text": "z"}
        sha256, size = chunker.entry_hash(data)
        entry = {
            "id": "c-x", "category": "event_log", "source_suffix": "live",
            "collected_at": "2026-10-28T17:00:00Z", "data": data,
            "sha256": sha256, "size": size,
        }
        assert _errors(evidence=[entry]), (seq, total)


def test_valid_chunk_chain_passes():
    data = {"blob": "q" * (30 * 1024)}
    raw = {
        "id": "c-doc", "category": "event_log", "source_suffix": "live",
        "collected_at": "2026-10-28T17:00:00Z", "data": data,
        "sha256": "pending", "size": 0,
    }
    chunks = chunker.chunk_entry(raw)
    assert len(chunks) >= 3
    assert chunker.validate_chunk_chain(chunks) == []
    errors, _ = manifest.validate_manifest(_manifest(evidence=chunks))
    assert errors == []


def test_dangling_refresh_of_rejected():
    entry = _entry()
    entry["refresh_of"] = "c-missing"
    assert _errors(evidence=[entry])


def test_bad_error_type():
    entry = _entry()
    entry["error"] = {"oops": True}
    assert _errors(evidence=[entry])


def test_bad_file_hashes():
    assert _errors(file_hashes={"../evil.txt": "a" * 64})
    assert _errors(file_hashes={"/abs.txt": "a" * 64})
    assert _errors(file_hashes={"ok.txt": "zzz"})
    assert _errors(file_hashes=[])
    assert _errors(file_hashes=None)


def test_file_hashes_ok_when_empty_or_valid():
    assert _errors(file_hashes={}) == []
    assert _errors(file_hashes={"notes/a.txt": "c" * 64}) == []


def test_manifest_sha256_stable():
    first = manifest.manifest_sha256(_manifest())
    second = manifest.manifest_sha256(copy.deepcopy(_manifest()))
    assert first == second and len(first) == 64


def test_new_package_id_is_uuid4():
    errors, _ = manifest.validate_manifest(_manifest(package_id=manifest.new_package_id()))
    assert errors == []
