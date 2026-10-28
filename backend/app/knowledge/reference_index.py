"""Gated reference-document index (FORGE 1D + D2 + D9).

Reference documents are background reading for technicians. They are kept
strictly separate from case memory (`KnowledgeEntry` / `KnowledgeMatch`):
this module never imports case-memory types, never returns them, and never
merges passages into them.

Security posture (D9): allowlisted manifest, per-file and total caps,
UTF-8 strict decoding, SHA-256 verification, symlink/traversal rejection,
and per-document quarantine. A bad document quarantines that document;
only a bad manifest itself fails the whole load.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = 1
MANIFEST_FILENAME = "reference_manifest.json"
REFERENCE_DIRNAME = "reference"

MAX_MANIFEST_BYTES = 64 * 1024
MAX_DOC_BYTES = 32 * 1024
MAX_TOTAL_BYTES = 256 * 1024
MAX_DOCS = 32
MAX_ANCHORS_PER_DOC = 32
MAX_SPANS_PER_DOC = 64
SPAN_MAX_CHARS = 500

ALLOWED_SUFFIX = ".md"
ALLOWED_LICENSES = frozenset({"forge-original"})

_DOC_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_ANCHOR_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*")
_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# Local stopwords (kept separate from case-memory signatures on purpose).
STOPWORDS = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those", "is",
        "are", "was", "were", "be", "been", "being", "it", "its", "of", "on",
        "in", "to", "for", "with", "and", "or", "but", "not", "no", "do",
        "does", "did", "have", "has", "had", "can", "could", "would", "should",
        "will", "please", "help", "me", "i", "am", "so", "very", "just",
        "when", "what", "which", "who", "how", "there", "here", "from",
    }
)


class ManifestError(ValueError):
    """Manifest-level failure: missing file, bad JSON, or bad schema major."""


@dataclass(frozen=True)
class ManifestEntry:
    doc_id: str
    path: str
    title: str
    anchors: tuple[str, ...]
    sha256: str
    license: str


@dataclass(frozen=True)
class QuarantinedDoc:
    doc_id: str
    path: str
    reason: str


@dataclass(frozen=True)
class ParsedSection:
    anchor: str
    heading: str
    body: str


@dataclass(frozen=True)
class LoadedDocument:
    entry: ManifestEntry
    text: str
    sections: tuple[ParsedSection, ...]
    size_bytes: int


@dataclass(frozen=True)
class Span:
    doc_id: str
    title: str
    path: str
    anchor: str
    heading: str
    text: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class LoadedCorpus:
    documents: tuple[LoadedDocument, ...]
    spans: tuple[Span, ...]
    quarantined: tuple[QuarantinedDoc, ...]
    warnings: tuple[str, ...] = ()
    manifest_path: str = ""


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parent / MANIFEST_FILENAME


def default_knowledge_dir() -> Path:
    return Path(__file__).resolve().parent


def slugify_heading(heading: str) -> str:
    lowered = (heading or "").strip().lower().replace("_", "-").replace(" ", "-")
    cleaned = re.sub(r"[^a-z0-9-]", "", lowered)
    collapsed = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return collapsed


def parse_sections(markdown_text: str) -> list[ParsedSection]:
    text = markdown_text or ""
    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        body = text.strip()
        if not body:
            return []
        return [ParsedSection(anchor="top", heading="", body=body)]
    sections: list[ParsedSection] = []
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        anchor = slugify_heading(heading) or "top"
        sections.append(ParsedSection(anchor=anchor, heading=heading, body=body))
    return sections


def tokenize(text: str, limit: int = 64) -> list[str]:
    tokens = _TOKEN_PATTERN.findall((text or "").lower())
    kept = sorted({t for t in tokens if len(t) >= 3 and t not in STOPWORDS})
    return kept[: max(1, limit)]


def truncate_span(text: str, max_chars: int = SPAN_MAX_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 2:
        return cleaned[:max_chars]
    budget = max_chars - 1  # room for ellipsis
    cut = cleaned[:budget]
    space = cut.rfind(" ")
    if space >= max(20, budget - 120):
        cut = cut[:space]
    return cut.rstrip() + "…"


def _split_section_body(body: str, max_chars: int = SPAN_MAX_CHARS) -> list[str]:
    cleaned = (body or "").strip()
    if not cleaned:
        return []
    if len(re.sub(r"\s+", " ", cleaned)) <= max_chars:
        return [truncate_span(cleaned, max_chars)]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        para_flat = re.sub(r"\s+", " ", para)
        if not current:
            if len(para_flat) <= max_chars:
                current = para_flat
            else:
                # Hard-split a long paragraph on word boundaries.
                words = para_flat.split(" ")
                piece = ""
                for word in words:
                    trial = f"{piece} {word}".strip()
                    if len(trial) <= max_chars:
                        piece = trial
                    else:
                        if piece:
                            chunks.append(piece)
                        piece = word[:max_chars]
                if piece:
                    chunks.append(piece)
        elif len(current) + 1 + len(para_flat) <= max_chars:
            current = f"{current} {para_flat}"
        else:
            chunks.append(current)
            if len(para_flat) <= max_chars:
                current = para_flat
            else:
                current = ""
                words = para_flat.split(" ")
                piece = ""
                for word in words:
                    trial = f"{piece} {word}".strip()
                    if len(trial) <= max_chars:
                        piece = trial
                    else:
                        if piece:
                            chunks.append(piece)
                        piece = word[:max_chars]
                if piece:
                    current = piece
    if current:
        chunks.append(current)
    return [truncate_span(c, max_chars) for c in chunks if c.strip()]


def _parse_schema_version(value: object) -> tuple[int, int]:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("Manifest missing required schema_version.")
    parts = value.strip().split(".")
    if len(parts) != 2:
        raise ManifestError(f"Bad schema_version {value!r}: want MAJOR.MINOR.")
    try:
        major = int(parts[0])
        minor = int(parts[1])
    except ValueError:
        raise ManifestError(f"Bad schema_version {value!r}: want MAJOR.MINOR.") from None
    return major, minor


def _coerce_entry(raw: object, index: int) -> ManifestEntry:
    if not isinstance(raw, dict):
        raise ManifestError(f"Manifest documents[{index}] must be an object.")
    doc_id = raw.get("doc_id")
    path = raw.get("path")
    title = raw.get("title")
    anchors = raw.get("anchors", raw.get("section_anchors"))
    sha256 = raw.get("sha256")
    license_tag = raw.get("license")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ManifestError(f"Manifest documents[{index}] missing doc_id.")
    if not isinstance(path, str) or not path.strip():
        raise ManifestError(f"Manifest documents[{index}] missing path.")
    if not isinstance(title, str) or not title.strip():
        raise ManifestError(f"Manifest documents[{index}] missing title.")
    if not isinstance(anchors, list) or not anchors:
        raise ManifestError(f"Manifest documents[{index}] missing anchors.")
    if not isinstance(sha256, str) or not sha256.strip():
        raise ManifestError(f"Manifest documents[{index}] missing sha256.")
    if not isinstance(license_tag, str) or not license_tag.strip():
        raise ManifestError(f"Manifest documents[{index}] missing license.")
    anchor_tuple = tuple(str(a).strip() for a in anchors)
    return ManifestEntry(
        doc_id=doc_id.strip(),
        path=path.strip(),
        title=title.strip(),
        anchors=anchor_tuple,
        sha256=sha256.strip().lower(),
        license=license_tag.strip(),
    )


def load_manifest(
    manifest_path: Path | None = None,
) -> tuple[list[ManifestEntry], list[str], Path]:
    resolved = Path(manifest_path) if manifest_path else default_manifest_path()
    try:
        raw_bytes = resolved.read_bytes()
    except FileNotFoundError:
        raise ManifestError(f"Reference manifest not found: {resolved}") from None
    except OSError as exc:
        raise ManifestError(f"Cannot read reference manifest: {exc}") from exc
    if len(raw_bytes) > MAX_MANIFEST_BYTES:
        raise ManifestError("Reference manifest exceeds size cap.")
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ManifestError(f"Reference manifest is not strict UTF-8: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Reference manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("Reference manifest root must be an object.")
    major, minor = _parse_schema_version(payload.get("schema_version"))
    warnings: list[str] = []
    if major != SCHEMA_MAJOR:
        raise ManifestError(
            f"Unsupported reference manifest major version {major}; want {SCHEMA_MAJOR}."
        )
    if f"{major}.{minor}" != SCHEMA_VERSION:
        warnings.append(
            f"Reference manifest minor version {major}.{minor} != {SCHEMA_VERSION}; continuing."
        )
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ManifestError("Reference manifest documents must be a list.")
    if len(documents) > MAX_DOCS:
        raise ManifestError(f"Reference manifest lists {len(documents)} docs; cap is {MAX_DOCS}.")
    entries: list[ManifestEntry] = []
    for i, raw in enumerate(documents):
        entries.append(_coerce_entry(raw, i))
    return entries, warnings, resolved


def _reject_path(path_value: str) -> str | None:
    if len(path_value) > 255:
        return "path exceeds 255 chars"
    if "\x00" in path_value:
        return "path contains NUL"
    lowered = path_value.replace("\\", "/")
    if lowered.startswith("/") or re.match(r"^[A-Za-z]:", path_value):
        return "absolute path or drive prefix rejected"
    # Normalise separators then look for traversal.
    import posixpath

    normalised = posixpath.normpath(lowered)
    if normalised == ".." or normalised.startswith("../") or "/../" in normalised:
        return "path traversal rejected"
    if not normalised.startswith(f"{REFERENCE_DIRNAME}/"):
        return f"path must stay under {REFERENCE_DIRNAME}/"
    if not normalised.endswith(ALLOWED_SUFFIX):
        return f"path must end with {ALLOWED_SUFFIX}"
    if normalized_parts_outside(normalised):
        return "path escapes reference dir"
    return None


def normalized_parts_outside(normalised: str) -> bool:
    parts = [p for p in normalised.split("/") if p not in ("", ".")]
    return not parts or parts[0] != REFERENCE_DIRNAME or any(p == ".." for p in parts)


def load_corpus(
    manifest_path: Path | None = None,
    knowledge_dir: Path | None = None,
) -> LoadedCorpus:
    entries, warnings, resolved_manifest = load_manifest(manifest_path)
    base = Path(knowledge_dir) if knowledge_dir else resolved_manifest.parent
    reference_dir = base / REFERENCE_DIRNAME

    documents: list[LoadedDocument] = []
    spans: list[Span] = []
    quarantined: list[QuarantinedDoc] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0

    for entry in entries:
        def _quarantine(reason: str) -> None:
            quarantined.append(
                QuarantinedDoc(doc_id=entry.doc_id, path=entry.path, reason=reason)
            )

        if entry.doc_id in seen_ids:
            _quarantine("duplicate doc_id")
            continue
        seen_ids.add(entry.doc_id)
        if not _DOC_ID_PATTERN.fullmatch(entry.doc_id):
            _quarantine("bad doc_id")
            continue
        if entry.path in seen_paths:
            _quarantine("duplicate path")
            continue
        seen_paths.add(entry.path)
        path_error = _reject_path(entry.path)
        if path_error:
            _quarantine(path_error)
            continue
        if not entry.title or len(entry.title) > 200:
            _quarantine("bad title")
            continue
        if not entry.anchors or len(entry.anchors) > MAX_ANCHORS_PER_DOC:
            _quarantine("anchor count out of range")
            continue
        bad_anchor = next(
            (a for a in entry.anchors if not _ANCHOR_PATTERN.fullmatch(a)), None
        )
        if bad_anchor is not None:
            _quarantine(f"bad anchor {bad_anchor!r}")
            continue
        if len(set(entry.anchors)) != len(entry.anchors):
            _quarantine("duplicate anchors")
            continue
        if not _SHA256_PATTERN.fullmatch(entry.sha256):
            _quarantine("bad sha256")
            continue
        if entry.license not in ALLOWED_LICENSES:
            _quarantine(f"unlisted license {entry.license!r}")
            continue

        # Resolve inside the knowledge dir; never follow symlinks out.
        candidate = base / entry.path.replace("\\", "/")
        try:
            if candidate.is_symlink():
                _quarantine("symlink rejected")
                continue
            if not candidate.is_file():
                _quarantine("file missing")
                continue
            # Containment: the resolved parent must stay under reference/.
            resolved_parent = candidate.resolve().parent
            allowed_root = reference_dir.resolve() if reference_dir.exists() else reference_dir
            try:
                resolved_parent.relative_to(allowed_root)
            except ValueError:
                # Fall back to string containment when the dir is missing.
                if allowed_root.as_posix() not in resolved_parent.as_posix():
                    _quarantine("path escapes reference dir")
                    continue
            size = candidate.stat().st_size
        except OSError as exc:
            _quarantine(f"unreadable file: {exc}")
            continue
        if size <= 0 or size > MAX_DOC_BYTES:
            _quarantine(f"size {size} out of range 1..{MAX_DOC_BYTES}")
            continue
        if total_bytes + size > MAX_TOTAL_BYTES:
            _quarantine("total corpus cap exceeded")
            continue
        try:
            raw_bytes = candidate.read_bytes()
        except OSError as exc:
            _quarantine(f"unreadable file: {exc}")
            continue
        # Hash LF-normalized bytes: manifest hashes are computed over LF, and
        # git autocrlf / Windows editors must not invalidate the corpus.
        digest = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest()
        if digest != entry.sha256:
            _quarantine("sha256 mismatch")
            continue
        try:
            text = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _quarantine("not strict UTF-8")
            continue

        parsed = parse_sections(text)
        if not parsed:
            _quarantine("empty document")
            continue
        parsed_by_anchor = {s.anchor: s for s in parsed}
        missing = [a for a in entry.anchors if a not in parsed_by_anchor]
        if missing:
            _quarantine(f"anchors missing from file: {', '.join(missing)}")
            continue
        extra = sorted(set(parsed_by_anchor) - set(entry.anchors))
        if extra:
            warnings.append(f"{entry.doc_id}: ignoring non-allowlisted sections: {', '.join(extra)}")

        allowlisted = [parsed_by_anchor[a] for a in entry.anchors]
        doc_spans: list[Span] = []
        for section in allowlisted:
            for chunk in _split_section_body(section.body):
                if len(doc_spans) >= MAX_SPANS_PER_DOC:
                    break
                tokens = tuple(tokenize(f"{section.heading} {chunk}"))
                doc_spans.append(
                    Span(
                        doc_id=entry.doc_id,
                        title=entry.title,
                        path=entry.path,
                        anchor=section.anchor,
                        heading=section.heading,
                        text=chunk,
                        tokens=tokens,
                    )
                )
            if len(doc_spans) >= MAX_SPANS_PER_DOC:
                break
        if not doc_spans:
            _quarantine("no indexable spans")
            continue
        total_bytes += size
        documents.append(
            LoadedDocument(
                entry=entry,
                text=text,
                sections=tuple(allowlisted),
                size_bytes=size,
            )
        )
        spans.extend(doc_spans)

    return LoadedCorpus(
        documents=tuple(documents),
        spans=tuple(spans),
        quarantined=tuple(quarantined),
        warnings=tuple(warnings),
        manifest_path=str(resolved_manifest),
    )
