"""Archive create + safe-extract gates (contracts section 2).

Covers traversal, bombs, hash mismatch, caps, and oversize rejection.
"""

import hashlib
import json
import os
import stat
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector import archive, chunker, manifest

HOST_HASH = "d" * 64
OS_INFO = {"platform": "p", "version": "v", "build": "b"}
PACKAGE_ID = "33333333-3333-4333-8333-333333333333"


def _entry(entry_id="c-1", category="os_info", data=None, **overrides):
    base = manifest.build_entry(
        entry_id=entry_id,
        category=category,
        data={"caption": "w"} if data is None else data,
        collected_at="2026-10-28T17:00:00Z",
    )
    base.update(overrides)
    return base


def _manifest(evidence=None, file_hashes=None, **overrides):
    base = manifest.build_manifest(
        hostname_hash=HOST_HASH,
        os_info=dict(OS_INFO),
        evidence=[_entry()] if evidence is None else evidence,
        file_hashes={} if file_hashes is None else file_hashes,
        package_id=PACKAGE_ID,
        created_at="2026-10-28T17:00:00Z",
    )
    base.update(overrides)
    return base


def _manifest_blob(mani):
    return json.dumps(mani, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_zip(path, members):
    """Write a raw ZIP; members maps name -> bytes (or ZipInfo tuple)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in members.items():
            zf.writestr(name, blob)
    return path


def _craft_valid(tmp_path, payloads=None):
    payloads = payloads or {"notes/a.txt": b"hello collector\n"}
    mani = _manifest(
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}
    )
    dest = tmp_path / "pkg.zip"
    archive.create_package(mani, payloads, dest)
    return dest, mani


def test_create_and_verify_roundtrip(tmp_path):
    dest, mani = _craft_valid(tmp_path)
    out, loaded, warnings = archive.extract_and_verify(dest, tmp_path / "out")
    assert loaded["package_id"] == mani["package_id"]
    assert (out / "notes" / "a.txt").read_text(encoding="utf-8").startswith("hello")
    assert warnings == []


def test_missing_manifest_rejected(tmp_path):
    path = _write_zip(tmp_path / "pkg.zip", {"notes/a.txt": b"x"})
    with pytest.raises(archive.ArchiveError):
        archive.safe_extract(path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "name", ["../evil.txt", "a/../../evil.txt", "/abs.txt", "C:/evil.txt", "C:\\evil.txt"]
)
def test_traversal_and_absolute_rejected(tmp_path, name):
    path = _write_zip(
        tmp_path / "pkg.zip", {"manifest.json": _manifest_blob(_manifest()), name: b"x"}
    )
    with pytest.raises(archive.ArchiveError):
        archive.safe_extract(path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_subdirectory_members_allowed(tmp_path):
    payloads = {"notes/deep/log.txt": b"deep\n"}
    mani = _manifest(
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}
    )
    dest = tmp_path / "pkg.zip"
    archive.create_package(mani, payloads, dest)
    out, _, _ = archive.extract_and_verify(dest, tmp_path / "out")
    assert (out / "notes" / "deep" / "log.txt").exists()


def _write_special(tmp_path, filename, mode_bits):
    path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _manifest_blob(_manifest()))
        info = zipfile.ZipInfo(filename)
        info.external_attr = (mode_bits & 0xFFFF) << 16
        zf.writestr(info, b"target")
    return path


def test_symlink_rejected(tmp_path):
    path = _write_special(tmp_path, "link", stat.S_IFLNK | 0o777)
    with pytest.raises(archive.ArchiveError, match="symlink"):
        archive.safe_extract(path, tmp_path / "out")


def test_device_node_rejected(tmp_path):
    path = _write_special(tmp_path, "dev", stat.S_IFCHR | 0o600)
    with pytest.raises(archive.ArchiveError, match="device"):
        archive.safe_extract(path, tmp_path / "out")


def test_fifo_rejected(tmp_path):
    path = _write_special(tmp_path, "pipe", stat.S_IFIFO | 0o600)
    with pytest.raises(archive.ArchiveError, match="fifo"):
        archive.safe_extract(path, tmp_path / "out")


def test_long_name_rejected(tmp_path):
    long_name = "n" * 250 + ".txt"  # 254 chars: ok
    archive.validate_member_name(long_name)
    too_long = "n" * 252 + ".txt"  # 256 chars: rejected
    with pytest.raises(archive.ArchiveError, match="255"):
        archive.validate_member_name(too_long)


@pytest.mark.parametrize("name", ["payload.exe", "no-suffix", "data.bin", "img.png"])
def test_bad_suffix_rejected(tmp_path, name):
    path = _write_zip(
        tmp_path / "pkg.zip", {"manifest.json": _manifest_blob(_manifest()), name: b"x"}
    )
    with pytest.raises(archive.ArchiveError, match="suffix"):
        archive.safe_extract(path, tmp_path / "out")


def test_per_file_cap(tmp_path):
    big = b"a" * (archive.MAX_FILE_BYTES + 1)
    mani = _manifest(file_hashes={"big.txt": hashlib.sha256(big).hexdigest()})
    with pytest.raises(archive.ArchiveError, match="2MB"):
        archive.create_package(mani, {"big.txt": big}, tmp_path / "pkg.zip")
    # And at extract time (hand-crafted zip bypassing create_package).
    path = _write_zip(
        tmp_path / "raw.zip",
        {"manifest.json": _manifest_blob(mani), "big.txt": big},
    )
    with pytest.raises(archive.ArchiveError, match="2MB"):
        archive.safe_extract(path, tmp_path / "out")


def test_total_cap_declared(tmp_path):
    # 21 x 1MB of zeros: tiny on disk, 21MB declared uncompressed.
    members = {"manifest.json": _manifest_blob(_manifest())}
    for i in range(21):
        members[f"files/f{i:03d}.txt"] = b"\x00" * (1024 * 1024)
    path = _write_zip(tmp_path / "pkg.zip", members)
    with pytest.raises(archive.ArchiveError, match="20MB"):
        archive.safe_extract(path, tmp_path / "out")


def test_file_count_cap(tmp_path):
    members = {"manifest.json": _manifest_blob(_manifest())}
    for i in range(archive.MAX_FILES):
        members[f"f{i:03d}.txt"] = b"x"
    path = _write_zip(tmp_path / "pkg.zip", members)
    with pytest.raises(archive.ArchiveError, match="200-file"):
        archive.safe_extract(path, tmp_path / "out")


def test_ratio_guard_rejects_bomb(tmp_path):
    bomb = b"\x00" * (1024 * 1024)  # ~1MB zeros -> ~1KB compressed (>50x)
    mani = _manifest(file_hashes={"bomb.txt": hashlib.sha256(bomb).hexdigest()})
    path = _write_zip(
        tmp_path / "pkg.zip", {"manifest.json": _manifest_blob(mani), "bomb.txt": bomb}
    )
    with pytest.raises(archive.ArchiveError, match="ratio"):
        archive.safe_extract(path, tmp_path / "out")


def test_normal_text_passes_ratio_guard(tmp_path):
    # Varied lines (timestamps, ids, rotating messages) like a real log.
    messages = [
        "service entered the running state", "service entered the stopped state",
        "tunnel re-establishment failed; retrying", "provider query completed",
        "checkpoint written to disk",
    ]
    lines = [
        f"2026-10-26T09:{i // 60:02d}:{i % 60:02d}Z id={7000 + (i % 37)} "
        f"provider=SCM msg=\"{messages[i % len(messages)]} (seq {i})\"\n"
        for i in range(2000)
    ]
    text = "".join(lines).encode()
    payloads = {"files/events.log": text}
    mani = _manifest(
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}
    )
    dest = tmp_path / "pkg.zip"
    archive.create_package(mani, payloads, dest)
    _, _, _ = archive.extract_and_verify(dest, tmp_path / "out")


def test_duplicate_names_rejected(tmp_path):
    path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _manifest_blob(_manifest()))
        zf.writestr("dup.txt", b"one")
        zf.writestr("dup.txt", b"two")
    with pytest.raises(archive.ArchiveError, match="duplicate"):
        archive.safe_extract(path, tmp_path / "out")


def test_not_a_zip_rejected(tmp_path):
    path = tmp_path / "pkg.zip"
    path.write_bytes(b"this is not a zip file")
    with pytest.raises(archive.ArchiveError):
        archive.safe_extract(path, tmp_path / "out")


def test_manifest_must_be_json_object(tmp_path):
    path = _write_zip(tmp_path / "pkg.zip", {"manifest.json": b"[1,2"})
    with pytest.raises(archive.ArchiveError):
        archive.read_manifest_from_zip(path)
    # Structural extraction succeeds (bytes + suffix are fine); full
    # verification rejects the malformed manifest.
    archive.safe_extract(path, tmp_path / "struct")
    with pytest.raises(archive.ArchiveError):
        archive.extract_and_verify(path, tmp_path / "out")


def test_hash_mismatch_rejects_whole_package(tmp_path):
    payloads = {"notes/a.txt": b"original\n"}
    mani = _manifest(
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}
    )
    dest = tmp_path / "pkg.zip"
    archive.create_package(mani, payloads, dest)
    # Tamper: rewrite the zip with altered payload bytes, same manifest.
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _manifest_blob(mani))
        zf.writestr("notes/a.txt", b"TAMPERED\n")
    # Structural extraction alone succeeds; full verification rejects.
    archive.safe_extract(tampered, tmp_path / "struct")
    with pytest.raises(archive.ArchiveError, match="hash mismatch"):
        archive.extract_and_verify(tampered, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_unlisted_extra_file_rejected(tmp_path):
    mani = _manifest(file_hashes={})
    path = _write_zip(
        tmp_path / "pkg.zip",
        {"manifest.json": _manifest_blob(mani), "notes/stowaway.txt": b"hi"},
    )
    with pytest.raises(archive.ArchiveError, match="unlisted"):
        archive.extract_and_verify(path, tmp_path / "out")


def test_missing_listed_file_rejected(tmp_path):
    mani = _manifest(file_hashes={"notes/ghost.txt": "e" * 64})
    path = _write_zip(tmp_path / "pkg.zip", {"manifest.json": _manifest_blob(mani)})
    with pytest.raises(archive.ArchiveError, match="missing"):
        archive.extract_and_verify(path, tmp_path / "out")


def test_oversize_entry_rejected_at_import(tmp_path):
    data = {"blob": "z" * (13 * 1024)}
    sha256, size = chunker.entry_hash(data)
    entry = {
        "id": "c-big", "category": "event_log", "source_suffix": "live",
        "collected_at": "2026-10-28T17:00:00Z", "data": data,
        "sha256": sha256, "size": size,
    }
    mani = _manifest(evidence=[entry])
    path = _write_zip(tmp_path / "pkg.zip", {"manifest.json": _manifest_blob(mani)})
    with pytest.raises(archive.ArchiveError, match="12KB"):
        archive.extract_and_verify(path, tmp_path / "out")


def test_safe_extract_refuses_nonempty_dest(tmp_path):
    dest, _ = _craft_valid(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "sentinel.txt").write_text("x")
    with pytest.raises(archive.ArchiveError, match="not empty"):
        archive.safe_extract(dest, out)


def test_create_package_validates_inputs(tmp_path):
    mani = _manifest(file_hashes={"a.txt": "f" * 64})
    with pytest.raises(archive.ArchiveError, match="mismatch"):
        archive.create_package(mani, {}, tmp_path / "pkg.zip")
    with pytest.raises(archive.ArchiveError, match="suffix"):
        archive.create_package(
            _manifest(file_hashes={"a.exe": hashlib.sha256(b"x").hexdigest()}),
            {"a.exe": b"x"},
            tmp_path / "pkg.zip",
        )
    bad_hash = _manifest(file_hashes={"a.txt": "0" * 64})
    with pytest.raises(archive.ArchiveError, match="file_hashes"):
        archive.create_package(bad_hash, {"a.txt": b"x"}, tmp_path / "pkg.zip")
    assert not (tmp_path / "pkg.zip").exists()


def test_read_manifest_from_zip(tmp_path):
    dest, mani = _craft_valid(tmp_path)
    loaded = archive.read_manifest_from_zip(dest)
    assert loaded["package_id"] == mani["package_id"]
    bad = _write_zip(tmp_path / "bad.zip", {"notes/a.txt": b"x"})
    with pytest.raises(archive.ArchiveError, match="manifest"):
        archive.read_manifest_from_zip(bad)
