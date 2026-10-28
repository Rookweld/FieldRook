"""Pre-chunk oversize evidence payloads (contracts v1, D3a).

Rule: a manifest entry's ``data`` object must be <= 12KB as canonical
JSON. Larger payloads MUST be pre-chunked by the collector into N
entries carrying ``chunk_seq``/``chunk_of`` in ``data`` plus a
``refresh_of`` chain linking chunk N to chunk N-1. Import rejects
unchunked >12KB items.

Canonical JSON (identical algorithm in ``hashverify.py``/``manifest.py``)::

    json.dumps(data, sort_keys=True, separators=(",", ":"),
               ensure_ascii=False, default=str).encode("utf-8")

Chunk layout per chunk ``seq`` of ``total`` (1-based):

- ``id``: ``"<orig-id>-c<seq>of<total>"`` (deterministic, unique);
- ``refresh_of``: previous chunk id (first chunk inherits the original
  ``refresh_of``, usually None);
- ``data``: ``{"chunk_seq", "chunk_of", "chunk_of_id", "encoding",
  "total_bytes", "chunk_text"}`` where the concatenated UTF-8 bytes of
  ``chunk_text`` slices decode to the original canonical JSON;
- ``sha256``/``size`` recomputed over each chunk's ``data``.

Stdlib only. No imports from this package.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = [
    "MAX_DATA_BYTES",
    "CHUNK_TEXT_BYTES",
    "CHUNK_ENCODING",
    "canonical_bytes",
    "data_size_bytes",
    "entry_hash",
    "needs_chunking",
    "chunk_entry",
    "chunk_entries",
    "unchunk_data",
    "validate_chunk_chain",
]

MAX_DATA_BYTES = 12 * 1024
# Slice budget leaving headroom for the chunk envelope (ids, hashes).
CHUNK_TEXT_BYTES = 10 * 1024
CHUNK_ENCODING = "json-utf8-slices"


def canonical_bytes(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def data_size_bytes(data: Any) -> int:
    return len(canonical_bytes(data))


def entry_hash(data: Any) -> tuple[str, int]:
    blob = canonical_bytes(data)
    return hashlib.sha256(blob).hexdigest(), len(blob)


def needs_chunking(data: Any) -> bool:
    return data_size_bytes(data) > MAX_DATA_BYTES


def _split_utf8(blob: bytes, budget: int) -> list[bytes]:
    """Split bytes on UTF-8 character boundaries."""
    parts: list[bytes] = []
    start = 0
    total = len(blob)
    while start < total:
        end = min(start + budget, total)
        # Back off from UTF-8 continuation bytes (10xxxxxx).
        while end > start and end < total and (blob[end] & 0xC0) == 0x80:
            end -= 1
        if end == start:  # degenerate: single char wider than budget
            end = start + budget
        parts.append(blob[start:end])
        start = end
    return parts or [b""]


def chunk_entry(entry: dict[str, Any], chunk_text_bytes: int = CHUNK_TEXT_BYTES) -> list[dict[str, Any]]:
    """Split one oversize entry into a chunk chain (no-op when small).

    The input entry must already carry ``id``/``category``/``data``; other
    fields (``source_suffix``, ``tool_name``, ``tool_args``,
    ``collected_at``, ``error``) are inherited by every chunk.
    """
    data = entry.get("data", {})
    if not needs_chunking(data):
        return [entry]
    blob = canonical_bytes(data)
    slices = _split_utf8(blob, chunk_text_bytes)
    total = len(slices)
    if total < 2:
        raise ValueError("payload exceeds 12KB but does not split; lower the slice budget.")
    base_id = str(entry.get("id", "ev"))
    chunks: list[dict[str, Any]] = []
    previous_id: str | None = entry.get("refresh_of")
    for seq, raw in enumerate(slices, start=1):
        chunk_id = f"{base_id}-c{seq}of{total}"
        chunk_data: dict[str, Any] = {
            "chunk_seq": seq,
            "chunk_of": total,
            "chunk_of_id": base_id,
            "encoding": CHUNK_ENCODING,
            "total_bytes": len(blob),
            "chunk_text": raw.decode("utf-8"),
        }
        sha256, size = entry_hash(chunk_data)
        if size > MAX_DATA_BYTES:
            raise ValueError(
                f"chunk {seq}/{total} still exceeds 12KB ({size} bytes); "
                "lower the slice budget."
            )
        chunk = {
            "id": chunk_id,
            "category": entry.get("category", ""),
            "source_suffix": entry.get("source_suffix", "live"),
            "collected_at": entry.get("collected_at", ""),
            "data": chunk_data,
            "sha256": sha256,
            "size": size,
        }
        for key in ("tool_name", "tool_args", "error"):
            if key in entry:
                chunk[key] = entry[key]
        chunk["refresh_of"] = previous_id
        chunks.append(chunk)
        previous_id = chunk_id
    return chunks


def chunk_entries(
    entries: list[dict[str, Any]], chunk_text_bytes: int = CHUNK_TEXT_BYTES
) -> tuple[list[dict[str, Any]], list[str]]:
    """Chunk every oversize entry; returns ``(entries, warnings)``."""
    out: list[dict[str, Any]] = []
    warnings: list[str] = []
    for entry in entries:
        chunks = chunk_entry(entry, chunk_text_bytes)
        if len(chunks) > 1:
            warnings.append(
                f"entry {entry.get('id')!r} pre-chunked into "
                f"{len(chunks)} parts (D3a)."
            )
        out.extend(chunks)
    return out, warnings


def unchunk_data(chunks: list[dict[str, Any]]) -> Any:
    """Reassemble ``chunk_text`` slices (in ``chunk_seq`` order) to data."""
    ordered = sorted(chunks, key=lambda e: e["data"]["chunk_seq"])
    blob = b"".join(c["data"]["chunk_text"].encode("utf-8") for c in ordered)
    return json.loads(blob.decode("utf-8"))


def validate_chunk_chain(entries: list[dict[str, Any]]) -> list[str]:
    """Validate ``chunk_seq``/``chunk_of``/``refresh_of`` chains."""
    errors: list[str] = []
    by_id = {e.get("id"): e for e in entries if isinstance(e, dict)}
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        data = entry.get("data", {}) if isinstance(entry, dict) else {}
        if not isinstance(data, dict):
            continue
        if "chunk_seq" in data or "chunk_of" in data:
            seq, total = data.get("chunk_seq"), data.get("chunk_of")
            if not isinstance(seq, int) or isinstance(seq, bool):
                errors.append(f"entry {entry.get('id')!r} has non-integer chunk_seq.")
                continue
            if not isinstance(total, int) or isinstance(total, bool):
                errors.append(f"entry {entry.get('id')!r} has non-integer chunk_of.")
                continue
            if total < 2:
                errors.append(f"entry {entry.get('id')!r} has chunk_of < 2.")
                continue
            if not 1 <= seq <= total:
                errors.append(f"entry {entry.get('id')!r} has chunk_seq out of range.")
                continue
            groups.setdefault(str(data.get("chunk_of_id", entry.get("id"))), []).append(entry)
    for group_id, parts in groups.items():
        totals = {p["data"]["chunk_of"] for p in parts}
        if len(totals) != 1:
            errors.append(f"chunk group {group_id!r} disagrees on chunk_of: {sorted(totals)}.")
            continue
        total = totals.pop()
        seqs = sorted(p["data"]["chunk_seq"] for p in parts)
        if seqs != list(range(1, total + 1)):
            errors.append(
                f"chunk group {group_id!r} has seqs {seqs}, expected 1..{total}."
            )
            continue
        by_seq = {p["data"]["chunk_seq"]: p for p in parts}
        for seq in range(2, total + 1):
            want = by_seq[seq - 1]["id"]
            got = by_seq[seq].get("refresh_of")
            if got != want:
                errors.append(
                    f"chunk {by_seq[seq]['id']!r} refresh_of={got!r}, "
                    f"expected previous chunk {want!r}."
                )
        for part in parts:
            ref = part.get("refresh_of")
            if ref is not None and ref not in by_id:
                errors.append(
                    f"chunk {part['id']!r} refresh_of={ref!r} is dangling."
                )
    return errors
