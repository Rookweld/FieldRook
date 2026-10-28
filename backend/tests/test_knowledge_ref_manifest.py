"""Gated corpus checks: allowlist, quarantine, hash, UTF-8, caps (D2/D9)."""

import hashlib
import json
from pathlib import Path

import pytest

from app.knowledge.reference_index import (
    MAX_ANCHORS_PER_DOC,
    MAX_DOC_BYTES,
    MAX_DOCS,
    SPAN_MAX_CHARS,
    ManifestError,
    load_corpus,
    load_manifest,
)

EXPECTED_IDS = {
    "ref-error-codes",
    "ref-service-recovery",
    "ref-dns-triage",
    "ref-crash-anatomy",
    "ref-app-launch",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_doc(root: Path, name: str, text: str) -> str:
    ref_dir = root / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    target = ref_dir / name
    target.write_text(text, encoding="utf-8")
    return _sha(target.read_bytes())


def _write_manifest(root: Path, entries: list[dict], version: str = "1.0") -> Path:
    manifest = root / "reference_manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": version, "documents": entries}, indent=2),
        encoding="utf-8",
    )
    return manifest


def _entry(doc_id: str, name: str, title: str, anchors: list[str], digest: str) -> dict:
    return {
        "doc_id": doc_id,
        "path": f"reference/{name}",
        "title": title,
        "anchors": anchors,
        "sha256": digest,
        "license": "forge-original",
    }


def test_default_corpus_loads_and_verifies() -> None:
    corpus = load_corpus()
    assert {d.entry.doc_id for d in corpus.documents} == EXPECTED_IDS
    assert corpus.quarantined == ()
    assert corpus.spans
    for span in corpus.spans:
        assert len(span.text) <= SPAN_MAX_CHARS
        assert span.anchor
        assert span.doc_id in EXPECTED_IDS
    for doc in corpus.documents:
        assert len(doc.sections) == 4


def test_allowlist_ignores_unlisted_file(tmp_path: Path) -> None:
    digest = _write_doc(tmp_path, "good.md", "# Good\n\n## Alpha Section\n\nAlpha content here.\n")
    _write_manifest(tmp_path, [_entry("ref-good", "good.md", "Good", ["alpha-section"], digest)])
    (tmp_path / "reference" / "evil-unlisted.md").write_text(
        "# Evil\n\n## Alpha Section\n\nUnlisted content must never load.\n", encoding="utf-8"
    )
    corpus = load_corpus(manifest_path=tmp_path / "reference_manifest.json")
    assert [d.entry.doc_id for d in corpus.documents] == ["ref-good"]
    assert corpus.quarantined == ()
    assert all("unlisted" not in s.text.lower() for s in corpus.spans)


def test_hash_mismatch_quarantines(tmp_path: Path) -> None:
    digest = _write_doc(tmp_path, "doc.md", "# T\n\n## Alpha Section\n\nOriginal words.\n")
    manifest = _write_manifest(tmp_path, [_entry("ref-doc", "doc.md", "T", ["alpha-section"], digest)])
    (tmp_path / "reference" / "doc.md").write_text(
        "# T\n\n## Alpha Section\n\nTampered words.\n", encoding="utf-8"
    )
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert len(corpus.quarantined) == 1
    assert "sha256" in corpus.quarantined[0].reason.lower()


def test_missing_file_quarantines(tmp_path: Path) -> None:
    fake = _sha(b"missing")
    manifest = _write_manifest(
        tmp_path, [_entry("ref-gone", "gone.md", "Gone", ["alpha-section"], fake)]
    )
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert "missing" in corpus.quarantined[0].reason.lower()


def test_bad_utf8_quarantines(tmp_path: Path) -> None:
    ref_dir = tmp_path / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    bad = b"# T\n\n## Alpha Section\n\nGood prefix \xff\xfe bad suffix\n"
    (ref_dir / "bad.md").write_bytes(bad)
    manifest = _write_manifest(
        tmp_path, [_entry("ref-bad", "bad.md", "Bad", ["alpha-section"], _sha(bad))]
    )
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert "utf-8" in corpus.quarantined[0].reason.lower()


def test_oversize_doc_quarantines(tmp_path: Path) -> None:
    big = "# T\n\n## Alpha Section\n\n" + ("x" * (MAX_DOC_BYTES + 10)) + "\n"
    digest = _write_doc(tmp_path, "big.md", big)
    manifest = _write_manifest(tmp_path, [_entry("ref-big", "big.md", "Big", ["alpha-section"], digest)])
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert "size" in corpus.quarantined[0].reason.lower()


def test_too_many_anchors_quarantines(tmp_path: Path) -> None:
    anchors = [f"section-{i}" for i in range(MAX_ANCHORS_PER_DOC + 1)]
    body = "# T\n\n" + "".join(f"## Section {i}\n\nWords here.\n\n" for i in range(len(anchors)))
    # Slugified anchors differ from section-N; force a count failure first.
    digest = _write_doc(tmp_path, "many.md", body)
    manifest = _write_manifest(tmp_path, [_entry("ref-many", "many.md", "Many", anchors, digest)])
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert "anchor" in corpus.quarantined[0].reason.lower()


def test_too_many_docs_rejects_manifest(tmp_path: Path) -> None:
    entries = []
    for i in range(MAX_DOCS + 1):
        name = f"d{i}.md"
        digest = _write_doc(tmp_path, name, "# T\n\n## Alpha Section\n\nWords.\n")
        entries.append(_entry(f"ref-d{i}", name, f"T{i}", ["alpha-section"], digest))
    manifest = _write_manifest(tmp_path, entries)
    with pytest.raises(ManifestError, match="cap"):
        load_manifest(manifest)


@pytest.mark.parametrize(
    "evil",
    [
        "../outside.md",
        "reference/../escape.md",
        "/absolute/path.md",
        "C:\\Windows\\evil.md",
        "other/dir.md",
        "reference/evil.txt",
    ],
)
def test_path_traversal_and_suffix_rejected(tmp_path: Path, evil: str) -> None:
    digest = _write_doc(tmp_path, "ok.md", "# T\n\n## Alpha Section\n\nWords.\n")
    entry = _entry("ref-evil", "ok.md", "Evil", ["alpha-section"], digest)
    entry["path"] = evil
    manifest = _write_manifest(tmp_path, [entry])
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert corpus.quarantined


def test_unlisted_license_quarantines(tmp_path: Path) -> None:
    digest = _write_doc(tmp_path, "doc.md", "# T\n\n## Alpha Section\n\nWords.\n")
    entry = _entry("ref-doc", "doc.md", "T", ["alpha-section"], digest)
    entry["license"] = "proprietary-unknown"
    manifest = _write_manifest(tmp_path, [entry])
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert "license" in corpus.quarantined[0].reason.lower()


def test_duplicate_doc_id_quarantines_second(tmp_path: Path) -> None:
    d1 = _write_doc(tmp_path, "a.md", "# A\n\n## Alpha Section\n\nFirst words.\n")
    d2 = _write_doc(tmp_path, "b.md", "# B\n\n## Alpha Section\n\nSecond words.\n")
    entries = [
        _entry("ref-dup", "a.md", "A", ["alpha-section"], d1),
        _entry("ref-dup", "b.md", "B", ["alpha-section"], d2),
    ]
    corpus = load_corpus(manifest_path=_write_manifest(tmp_path, entries))
    assert len(corpus.documents) == 1
    assert len(corpus.quarantined) == 1
    assert "duplicate" in corpus.quarantined[0].reason.lower()


def test_anchor_mismatch_quarantines(tmp_path: Path) -> None:
    digest = _write_doc(tmp_path, "doc.md", "# T\n\n## Alpha Section\n\nWords.\n")
    manifest = _write_manifest(
        tmp_path, [_entry("ref-doc", "doc.md", "T", ["no-such-section"], digest)]
    )
    corpus = load_corpus(manifest_path=manifest)
    assert corpus.documents == ()
    assert "anchor" in corpus.quarantined[0].reason.lower()


def test_schema_major_rejects(tmp_path: Path) -> None:
    digest = _write_doc(tmp_path, "doc.md", "# T\n\n## Alpha Section\n\nWords.\n")
    manifest = _write_manifest(
        tmp_path, [_entry("ref-doc", "doc.md", "T", ["alpha-section"], digest)], version="2.0"
    )
    with pytest.raises(ManifestError, match="major"):
        load_corpus(manifest_path=manifest)


def test_schema_minor_warns_but_loads(tmp_path: Path) -> None:
    digest = _write_doc(tmp_path, "doc.md", "# T\n\n## Alpha Section\n\nWords here.\n")
    manifest = _write_manifest(
        tmp_path, [_entry("ref-doc", "doc.md", "T", ["alpha-section"], digest)], version="1.1"
    )
    corpus = load_corpus(manifest_path=manifest)
    assert len(corpus.documents) == 1
    assert any("1.1" in w for w in corpus.warnings)


def test_bad_manifest_json_fails_closed(tmp_path: Path) -> None:
    manifest = tmp_path / "reference_manifest.json"
    manifest.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="JSON"):
        load_corpus(manifest_path=manifest)


def test_missing_manifest_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not found"):
        load_corpus(manifest_path=tmp_path / "nope.json")
