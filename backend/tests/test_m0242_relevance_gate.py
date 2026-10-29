"""M024.2: knowledge relevance gate before excerpts enter model context.

The M024.1 blind evaluation showed purely lexical ranking injects
topically irrelevant excerpts whenever a query shares generic filler
vocabulary with a document (filler can be corpus-rare yet carry no
topical signal). These tests pin the gate rule: a passage is kept iff
at least one explainable criterion fires (error-code, subsystem title
topic, evidence term, or discriminating problem term).

All queries below are synthetic. None reuse evaluation scenario text:
the gate must follow the general rule, never per-scenario special
cases (see test_gate_has_no_scenario_special_cases).
"""

from pathlib import Path

from app.analysis.loop import reference_excerpts_for
from app.knowledge.reference_index import load_corpus
from app.knowledge.reference_service import match_references
from app.knowledge.relevance_gate import (
    GENERIC_TERMS,
    MAX_DISCRIMINATING_DF,
    GateVerdict,
    document_frequencies,
    is_discriminating,
    is_error_code,
    judge_passage,
)

GENERIC_ONLY_QUERY = (
    "A client user cannot open the shared machine for review every afternoon"
)
TOPICAL_QUERIES: list[tuple[str, str]] = [
    ("DNS resolution fails with a timeout", "ref-dns-triage"),
    ("Print Spooler stopped; recovery actions keep firing", "ref-service-recovery"),
    ("How do I read facility bits in error code 0x80070005?", "ref-error-codes"),
    ("Crash names a faulting module and exception code", "ref-crash-anatomy"),
    ("The app will not launch; the window never appears", "ref-app-launch"),
]


def test_error_code_pattern() -> None:
    assert is_error_code("0x80070005")
    assert is_error_code("0xc0000005")
    assert is_error_code("1000")
    assert is_error_code("7036")
    assert not is_error_code("dns")
    assert not is_error_code("0x")
    assert not is_error_code("42")
    assert not is_error_code("1080p")


def test_document_frequencies_measure_topicality() -> None:
    corpus = load_corpus()
    assert len(corpus.documents) == 5
    df = document_frequencies(corpus)
    # Topical terms stay rare; corpus-ubiquitous filler does not discriminate.
    assert df.get("dns", 99) <= MAX_DISCRIMINATING_DF
    assert df.get("recovery", 99) <= MAX_DISCRIMINATING_DF
    assert df.get("spooler", 0) == 0  # never in corpus: inert, never generic
    # "service" is shared across docs yet topical in combination (F3 lesson).
    assert df.get("service", 0) == MAX_DISCRIMINATING_DF
    assert df.get("note", 0) > MAX_DISCRIMINATING_DF
    assert df.get("collect", 0) > MAX_DISCRIMINATING_DF


def test_generic_vocabulary_contract() -> None:
    assert len(GENERIC_TERMS) > 50
    for term in GENERIC_TERMS:
        assert term == term.lower()
        assert len(term) >= 3
        assert " " not in term
    # Filler that caused the M024.1 mispriming is generic ...
    for filler in ("client", "user", "cannot", "open", "every", "needs", "review"):
        assert filler in GENERIC_TERMS
    # ... while subsystem / product / state words are never generic.
    for topical in (
        "dns", "spooler", "recovery", "license", "faulting", "printer",
        "vpn", "outlook", "mailbox", "server", "service", "stopped",
        "running", "error", "code",
    ):
        if topical == "error":
            assert topical in GENERIC_TERMS  # bare "error" alone is content-free
        else:
            assert topical not in GENERIC_TERMS


def test_is_discriminating_combines_rarity_and_generality() -> None:
    df = {"dns": 1, "client": 1, "service": 3, "any": 5}
    assert is_discriminating("dns", df)
    assert not is_discriminating("client", df)  # rare but generic filler
    assert is_discriminating("service", df)  # at threshold: needs a pair
    assert not is_discriminating("any", df)  # corpus-ubiquitous filler


def test_judge_error_code_reason() -> None:
    verdict = judge_passage(
        p_hit={"1000", "event"},
        s_hit=set(),
        e_hit=set(),
        t_hit=set(),
        df={"1000": 1, "event": 2},
    )
    assert verdict.passed
    assert any(r.startswith("error-code:") for r in verdict.reasons)


def test_judge_subsystem_title_reason() -> None:
    verdict = judge_passage(
        p_hit={"dns"},
        s_hit=set(),
        e_hit=set(),
        t_hit={"dns"},
        df={"dns": 1},
    )
    assert verdict.passed
    assert "subsystem:dns" in verdict.reasons


def test_judge_evidence_reason() -> None:
    verdict = judge_passage(
        p_hit=set(),
        s_hit=set(),
        e_hit={"dns"},
        t_hit=set(),
        df={"dns": 1},
    )
    assert verdict.passed
    assert "evidence:dns" in verdict.reasons


def test_judge_generic_only_filtered_with_explanation() -> None:
    verdict = judge_passage(
        p_hit={"client", "needs", "review"},
        s_hit=set(),
        e_hit=set(),
        t_hit={"review"},
        df={"client": 1, "needs": 1, "review": 1},
    )
    assert verdict == GateVerdict(passed=False, reasons=verdict.reasons)
    assert not verdict.passed
    assert len(verdict.reasons) == 1
    assert verdict.reasons[0].startswith("generic-only:")


def test_generic_only_query_yields_no_excerpts() -> None:
    assert match_references(GENERIC_ONLY_QUERY) == []
    # The gate is the mechanism: ranking alone still finds the filler match.
    ungated = match_references(GENERIC_ONLY_QUERY, relevance_gate=False)
    assert ungated, "expected the raw lexical match the gate must remove"


def test_topical_queries_keep_expected_doc_first() -> None:
    for problem, expected in TOPICAL_QUERIES:
        ranked = match_references(problem, limit=5)
        assert ranked, f"gate must not starve topical query: {problem}"
        assert ranked[0].doc_id == expected


def test_subsystem_topic_passes_without_pair() -> None:
    # A title/heading topic is a strong signal on its own.
    ranked = match_references("DNS")
    assert ranked
    assert ranked[0].doc_id == "ref-dns-triage"


def test_coherent_common_terms_pass() -> None:
    # Individually corpus-wide subsystem words ("service", "start",
    # "stopped") still carry topical signal in combination.
    problem = "The app service will not start; it shows stopped"
    assert match_references(problem, relevance_gate=False)
    ranked = match_references(problem)
    assert ranked
    assert ranked[0].doc_id == "ref-service-recovery"


def test_lone_rare_term_is_filtered() -> None:
    # One lone rare word is not relevance: "shared" must not pull a
    # crash note into a sync case.
    assert match_references("shared input", relevance_gate=False)
    assert match_references("shared input") == []
    verdict = judge_passage(
        p_hit={"shared"},
        s_hit=set(),
        e_hit=set(),
        t_hit=set(),
        df={"shared": 1},
    )
    assert not verdict.passed


def test_gate_preserves_scores_and_order() -> None:
    problem = "DNS resolution fails with a timeout; check the server list"
    gated = match_references(problem, limit=5)
    ungated = match_references(problem, limit=5, relevance_gate=False)
    assert gated
    assert [(p.doc_id, p.score) for p in gated] == [
        (p.doc_id, p.score) for p in ungated if p in gated
    ]


def test_reference_excerpts_for_empty_when_irrelevant() -> None:
    assert reference_excerpts_for(GENERIC_ONLY_QUERY) == []


def test_reference_excerpts_for_keeps_citations_when_topical() -> None:
    excerpts = reference_excerpts_for("DNS does not resolve on the field laptop")
    assert len(excerpts) >= 1
    first = excerpts[0]
    assert set(first) == {"doc_id", "title", "path", "anchor", "span"}
    assert first["doc_id"] == "ref-dns-triage"
    assert first["path"].endswith(".md")
    assert first["anchor"]


def test_gate_has_no_scenario_special_cases() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "knowledge"
        / "relevance_gate.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "cad-license", "solidedge", "webcam", "bsod", "onedrive", "monitor-",
        "mailbox", "outlook", "forge-", "intranet", "payroll", "spooler",
        "vpn", "teams", "0117", "heldout",
    )
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered, f"gate must not name {token}"
