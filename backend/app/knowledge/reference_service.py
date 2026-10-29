"""Ranked reference-passage retrieval (FORGE 1D).

Case memory (`KnowledgeMatch`) and reference documents (`ReferencePassage`)
are separate types and never merge. This module defines the reference side
only: lexical ranking over the gated corpus, citation building, and quoted
technician-visible rendering.

Injection rule: reference text reaches the model ONLY as a quoted excerpt
inside a templated technician-visible message, never as a system
instruction. Renderers must use `format_quoted_excerpt` /
`build_technician_message`; raw spans are never instructions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .reference_index import (
    LoadedCorpus,
    ManifestError,
    load_corpus,
    tokenize,
)
from .relevance_gate import document_frequencies, judge_passage

# Display-only reliability ordering (no percentages). Higher rank = stronger.
# MEASURED > TECH_CONFIRMED > VENDOR_DOC > COMMUNITY > INFERRED.
RELIABILITY_MEASURED = "MEASURED"
RELIABILITY_TECH_CONFIRMED = "TECH_CONFIRMED"
RELIABILITY_VENDOR_DOC = "VENDOR_DOC"
RELIABILITY_COMMUNITY = "COMMUNITY"
RELIABILITY_INFERRED = "INFERRED"

RELIABILITY_ORDER: tuple[str, ...] = (
    RELIABILITY_MEASURED,
    RELIABILITY_TECH_CONFIRMED,
    RELIABILITY_VENDOR_DOC,
    RELIABILITY_COMMUNITY,
    RELIABILITY_INFERRED,
)

RELIABILITY_RANK: dict[str, int] = {
    name: len(RELIABILITY_ORDER) - i for i, name in enumerate(RELIABILITY_ORDER)
}

# Seed corpus is original prose: useful background, never measured evidence.
DEFAULT_REFERENCE_RELIABILITY = RELIABILITY_COMMUNITY

REFERENCE_DISCLAIMER = "Reference excerpt, not a diagnosis."

# Inspectable integer weights (no hidden scores, no percentages).
W_PROBLEM = 1
W_PROBLEM_CAP = 5
W_SERVICE = 3
W_SERVICE_CAP = 3
W_EVIDENCE = 2
W_EVIDENCE_CAP = 10
W_TITLE = 2
W_TITLE_CAP = 3
MIN_SCORE = 2
MAX_MATCHES = 20
SPAN_MAX_CHARS = 500


class ReferencePassage(BaseModel):
    """One ranked reference excerpt. Background reading, never a diagnosis."""

    schema_version: str = Field(default="1.0")
    doc_id: str
    title: str
    path: str
    anchor: str
    span: str
    score: int
    terms: list[str] = Field(default_factory=list)


class ReferenceCitation(BaseModel):
    """Attribution for one passage. kind is always 'reference'."""

    schema_version: str = Field(default="1.0")
    kind: Literal["reference"] = "reference"
    doc_id: str
    title: str
    locator: str


def is_more_reliable(left: str, right: str) -> bool:
    return RELIABILITY_RANK.get(left, 0) > RELIABILITY_RANK.get(right, 0)


def locator_for(path: str, anchor: str) -> str:
    return f"{path}#{anchor}"


def build_citation(passage: ReferencePassage) -> ReferenceCitation:
    return ReferenceCitation(
        doc_id=passage.doc_id,
        title=passage.title,
        locator=locator_for(passage.path, passage.anchor),
    )


def build_citations(passages: list[ReferencePassage]) -> list[ReferenceCitation]:
    return [build_citation(p) for p in passages]


def _redact_text(text: str) -> str:
    # FUTURE shared-redact reuse: replace this local wrapper with the shared
    # backend/app/redact/ core once the lead promotes it (FORGE D4a).
    # Local behaviour today: reuse the knowledge redactor when available.
    try:
        from .redact import redact_text as _knowledge_redact
    except Exception:  # noqa: BLE001 - fail closed to unredacted text
        return text or ""
    try:
        return _knowledge_redact(text or "")
    except Exception:  # noqa: BLE001 - never fail ranking on redaction
        return text or ""


def _truncate_span(text: str, max_chars: int = SPAN_MAX_CHARS) -> str:
    # Local span truncation (kept in-service so rendering never depends on
    # index internals). Word-boundary cut with an ellipsis, capped at 500ch.
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 2:
        return cleaned[:max_chars]
    budget = max_chars - 1
    cut = cleaned[:budget]
    space = cut.rfind(" ")
    if space >= max(20, budget - 120):
        cut = cut[:space]
    return cut.rstrip() + "…"


def format_quoted_excerpt(passage: ReferencePassage) -> str:
    """Render one passage as a quoted, attributed block (fail-closed shape).

    Every content line is prefixed with '> ' so instruction-like words inside
    a document stay inside the quote. Attribution and disclaimer always follow.
    """
    locator = locator_for(passage.path, passage.anchor)
    body = _truncate_span(_redact_text(passage.span), SPAN_MAX_CHARS)
    quoted_lines = [f"> {line}" if line.strip() else ">" for line in body.split("\n")]
    quoted = "\n".join(quoted_lines) if quoted_lines else ">"
    return (
        f"{REFERENCE_DISCLAIMER} From {passage.title} [{passage.doc_id}] ({locator}):\n"
        f"{quoted}\n"
        f"— {passage.title} ({locator})"
    )


def build_technician_message(
    passages: list[ReferencePassage], problem: str = ""
) -> str:
    """Templated technician-visible message carrying only quoted excerpts."""
    headline = _truncate_span(problem or "current issue", 200)
    lines = [
        f"Reference notes for: {headline}",
        "The excerpts below are background reading, not diagnoses. "
        "Verify against measured evidence before acting.",
        "",
    ]
    if not passages:
        lines.append("(No reference excerpts matched. Collect more evidence.)")
        return "\n".join(lines) + "\n"
    for i, passage in enumerate(passages, start=1):
        lines.append(f"[{i}] {format_quoted_excerpt(passage)}")
        lines.append("")
    lines.append("Steps derived from these notes still need independent checks.")
    return "\n".join(lines).rstrip() + "\n"


def _overlap(query: set[str], span_tokens: set[str]) -> set[str]:
    return set(query) & set(span_tokens)


def match_references(
    problem: str,
    service: str | None = None,
    evidence_terms: list[str] | None = None,
    limit: int = 5,
    manifest_path: Path | str | None = None,
    corpus: LoadedCorpus | None = None,
    relevance_gate: bool = True,
) -> list[ReferencePassage]:
    """Rank reference spans for a problem. Never returns `KnowledgeMatch`.

    Args:
        problem: Free-text problem statement.
        service: Optional service or app name for a title/identity boost.
        evidence_terms: Optional measured terms (codes, names, keywords).
        limit: Max passages (1..20); non-positive returns [].
        manifest_path: Test hook to load a custom gated corpus.
        corpus: Test hook with an already-loaded corpus (wins over manifest).
        relevance_gate: Drop passages matched purely on generic filler (M024.2).

    Returns:
        Ranked `ReferencePassage` list, highest score first. [] when nothing
        scores at threshold, the corpus fails closed, or no passage passes
        the relevance gate.
    """
    if limit is None or limit <= 0:
        return []
    bounded = max(1, min(int(limit), MAX_MATCHES))

    problem_tokens = set(tokenize(problem or "", limit=40))
    service_tokens = set(tokenize(service or "", limit=10))
    flattened_evidence: set[str] = set()
    for term in evidence_terms or []:
        if not term:
            continue
        if isinstance(term, str):
            flattened_evidence.update(tokenize(term, limit=10))
        else:
            flattened_evidence.update(tokenize(str(term), limit=10))
    if not problem_tokens and not service_tokens and not flattened_evidence:
        return []

    if corpus is None:
        try:
            resolved = Path(manifest_path) if manifest_path else None
            corpus = load_corpus(manifest_path=resolved)
        except ManifestError:
            return []  # fail closed on manifest-level failure
        except OSError:
            return []
        except ValueError:
            return []
    if not corpus.spans:
        return []

    query_all = problem_tokens | service_tokens | flattened_evidence
    ranked: list[ReferencePassage] = []
    hit_sets: list[tuple[set[str], set[str], set[str], set[str]]] = []
    for span in corpus.spans:
        span_set = set(span.tokens)
        p_hit = _overlap(problem_tokens, span_set)
        s_hit = _overlap(service_tokens, span_set)
        e_hit = _overlap(flattened_evidence, span_set)
        title_set = set(tokenize(f"{span.title} {span.heading}", limit=20))
        t_hit = _overlap(query_all, title_set)
        score = (
            min(len(p_hit), W_PROBLEM_CAP) * W_PROBLEM
            + min(len(s_hit), W_SERVICE_CAP) * W_SERVICE
            + min(len(e_hit), W_EVIDENCE_CAP) * W_EVIDENCE
            + min(len(t_hit), W_TITLE_CAP) * W_TITLE
        )
        if score < MIN_SCORE:
            continue
        matched = sorted(p_hit | s_hit | e_hit | t_hit)
        redacted = _redact_text(span.text)
        final_span = _truncate_span(redacted, SPAN_MAX_CHARS)
        ranked.append(
            ReferencePassage(
                doc_id=span.doc_id,
                title=span.title,
                path=span.path,
                anchor=span.anchor,
                span=final_span,
                score=int(score),
                terms=matched,
            )
        )
        hit_sets.append((p_hit, s_hit, e_hit, t_hit))
    order = sorted(
        range(len(ranked)),
        key=lambda i: (
            -ranked[i].score,
            ranked[i].doc_id,
            ranked[i].anchor,
            ranked[i].span[:64],
        ),
    )
    ranked = [ranked[i] for i in order]
    hit_sets = [hit_sets[i] for i in order]
    if relevance_gate:
        # M024.2: ranking is unchanged; passages matched purely on generic
        # shared vocabulary are withheld before they can enter model context.
        df = document_frequencies(corpus)
        ranked = [
            passage
            for passage, hits in zip(ranked, hit_sets)
            if judge_passage(*hits, df).passed
        ]
    return ranked[:bounded]
