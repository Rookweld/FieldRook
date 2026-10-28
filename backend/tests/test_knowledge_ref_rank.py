"""Ranking quality on fixed queries (FORGE 1D)."""

from app.knowledge.reference_service import (
    DEFAULT_REFERENCE_RELIABILITY,
    RELIABILITY_COMMUNITY,
    RELIABILITY_INFERRED,
    RELIABILITY_MEASURED,
    RELIABILITY_ORDER,
    RELIABILITY_TECH_CONFIRMED,
    RELIABILITY_VENDOR_DOC,
    ReferencePassage,
    build_citation,
    is_more_reliable,
    match_references,
)
from app.schemas import KnowledgeMatch

FIXED_QUERIES: list[tuple[str, str | None, list[str], str]] = [
    (
        "How do I read Windows error code 0x80070005? The hex code shows "
        "access denied and I need to look up the facility and severity bits.",
        None,
        ["0x80070005", "facility"],
        "ref-error-codes",
    ),
    (
        "Print Spooler service stopped and will not start. Startup type is "
        "automatic, recovery actions keep restarting it, dependencies look odd.",
        "Spooler",
        ["service", "recovery"],
        "ref-service-recovery",
    ),
    (
        "DNS resolution fails with timeout. Cannot resolve hostname, cache "
        "looks stale, need to check resolvers and forwarders.",
        None,
        ["DNS", "NXDOMAIN", "timeout"],
        "ref-dns-triage",
    ),
    (
        "Application crashed, event log shows Event 1000 with faulting module "
        "and exception code 0xc0000005.",
        None,
        ["1000", "faulting module", "exception"],
        "ref-crash-anatomy",
    ),
    (
        "App will not launch, double-click does nothing, no window appears, "
        "process exits silently.",
        None,
        ["launch", "silent exit"],
        "ref-app-launch",
    ),
]


def test_fixed_queries_rank_expected_doc_first() -> None:
    for problem, service, evidence_terms, expected in FIXED_QUERIES:
        matches = match_references(problem, service, evidence_terms, limit=5)
        assert matches, f"no matches for {expected}"
        assert matches[0].doc_id == expected, (
            f"want {expected} first, got {[m.doc_id for m in matches]}"
        )
        for passage in matches:
            assert isinstance(passage.score, int)
            assert passage.score >= 2
            assert 0 < len(passage.span) <= 500
            assert passage.terms
            assert passage.anchor
            citation = build_citation(passage)
            assert citation.kind == "reference"
            assert citation.doc_id == passage.doc_id
            assert citation.locator == f"{passage.path}#{passage.anchor}"


def test_limit_respected_and_capped() -> None:
    problem = FIXED_QUERIES[0][0]
    assert match_references(problem, limit=2).__len__() <= 2
    assert match_references(problem, limit=0) == []
    assert match_references(problem, limit=-3) == []
    capped = match_references(problem, limit=100)
    assert len(capped) <= 20


def test_empty_query_returns_empty() -> None:
    assert match_references("") == []
    assert match_references("   ", None, None) == []
    assert match_references("", None, []) == []


def test_evidence_terms_rescue_generic_problem() -> None:
    ranked = match_references(
        "Something failed on this computer.",
        None,
        ["DNS", "NXDOMAIN", "timeout", "resolver"],
        limit=3,
    )
    assert ranked
    assert ranked[0].doc_id == "ref-dns-triage"


def test_service_param_boosts_service_doc() -> None:
    ranked = match_references("It stopped again last night.", "Spooler", [], limit=3)
    # Service token alone may not clear threshold; with recovery context it must.
    ranked2 = match_references(
        "It stopped again last night, recovery actions fired.", "Spooler", [], limit=3
    )
    assert ranked2
    assert ranked2[0].doc_id == "ref-service-recovery"
    assert ranked == [] or all(isinstance(p, ReferencePassage) for p in ranked)


def test_passages_never_merge_into_knowledge_match() -> None:
    matches = match_references(FIXED_QUERIES[2][0], None, ["DNS"], limit=3)
    assert matches
    for passage in matches:
        assert isinstance(passage, ReferencePassage)
        assert not isinstance(passage, KnowledgeMatch)
        assert not hasattr(passage, "entry")
        assert not hasattr(passage, "strength")
        # Contract shape only.
        assert set(passage.model_dump()) == {
            "schema_version",
            "doc_id",
            "title",
            "path",
            "anchor",
            "span",
            "score",
            "terms",
        }


def test_scores_deterministic() -> None:
    problem, service, terms, _ = FIXED_QUERIES[3]
    first = [(p.doc_id, p.anchor, p.score) for p in match_references(problem, service, terms)]
    second = [(p.doc_id, p.anchor, p.score) for p in match_references(problem, service, terms)]
    assert first == second


def test_reliability_rank_constants() -> None:
    assert RELIABILITY_ORDER == (
        RELIABILITY_MEASURED,
        RELIABILITY_TECH_CONFIRMED,
        RELIABILITY_VENDOR_DOC,
        RELIABILITY_COMMUNITY,
        RELIABILITY_INFERRED,
    )
    assert is_more_reliable(RELIABILITY_MEASURED, RELIABILITY_TECH_CONFIRMED)
    assert is_more_reliable(RELIABILITY_TECH_CONFIRMED, RELIABILITY_VENDOR_DOC)
    assert is_more_reliable(RELIABILITY_VENDOR_DOC, RELIABILITY_COMMUNITY)
    assert is_more_reliable(RELIABILITY_COMMUNITY, RELIABILITY_INFERRED)
    assert not is_more_reliable(RELIABILITY_INFERRED, RELIABILITY_MEASURED)
    assert DEFAULT_REFERENCE_RELIABILITY == RELIABILITY_COMMUNITY
    assert DEFAULT_REFERENCE_RELIABILITY not in {
        RELIABILITY_MEASURED,
        RELIABILITY_TECH_CONFIRMED,
    }
