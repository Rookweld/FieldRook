"""Knowledge relevance gate (M024.2, lead-owned hardening).

Why: blind evaluation showed that purely lexical ranking can inject
topically irrelevant excerpts into model context whenever a query shares
generic filler vocabulary with a document. In a small curated corpus,
filler words ("client", "review", "every") can be rare yet carry no
topical signal at all, and small models are easily primed by the
injected text. Retrieval quality bounds troubleshooting quality.

What: a conservative second-stage filter over ranked reference
passages. Ranking (scores, order) is unchanged; a passage is then KEPT
iff at least one explainable relevance criterion fires:

- error-code: query and passage share a code-like token (0x-hex or a
  3+ digit number such as an event id).
- subsystem: a discriminating query token hits the document title or
  section heading, i.e. the document is ABOUT the query topic.
- evidence: a discriminating measured evidence term hits the passage.
- topic: at least two distinct discriminating problem/service tokens
  hit, i.e. a coherent topical combination rather than one lone word.

A token is discriminating iff it occurs in at most
MAX_DISCRIMINATING_DF documents AND is not generic English / generic
IT filler (GENERIC_TERMS). Document frequency alone cannot carry the
gate in either direction: rarity in a small corpus is not topicality
("client", "review"), and corpus-wide subsystem words ("service",
"start") still carry topical signal in combination. Conversely the
generic list holds only words that are subsystem-agnostic in every
plausible troubleshooting context; subsystem, product, device, state,
and error-vocabulary words are deliberately NOT generic, even when
they are absent from the current corpus.

The gate is deliberately conservative (OR over criteria): it removes
only matches built purely from generic shared vocabulary or from a
single lone term. When nothing is sufficiently relevant, callers get
[] and send no knowledge block.

Boundaries preserved: ReferencePassage / ReferenceCitation shapes are
untouched, excerpts still reach the model only as quoted
technician-visible context, and the gate never sees scenario identity:
no per-scenario, per-document, or per-case special-casing exists here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .reference_index import LoadedCorpus, tokenize

# A token shared by more documents than this carries no topical signal on
# its own. Absolute count, not a fraction: single-document test corpora
# must keep working, and the seed corpus is hash-gated so this number
# cannot drift silently. Revisit if the corpus grows an order of
# magnitude. Three (not two): subsystem words such as "service" legitimately
# appear across the seed docs, and the two-topic-term rule below keeps
# them honest in combination.
MAX_DISCRIMINATING_DF = 3

# An exact shared code token is relevant on its own: 0x-hex values and
# 3+ digit numbers (event ids, Win32 / HTTP style codes).
_CODE_RE = re.compile(r"^(?:0x[0-9a-f]{2,}|[0-9]{3,})$")

# Generic English + generic IT filler: words that identify no subsystem
# in any plausible troubleshooting context. Deliberately NOT here:
# subsystem words (dns, server, network, service, driver, printer),
# product names, device words, state words (running, stopped, started,
# paused, automatic, manual, disabled, enabled, healthy), error
# vocabulary (code, message, text, offset, exception, hex, facility),
# recovery vocabulary, or action words tied to a subsystem. A term that
# is merely absent from today's corpus stays out: absence is not
# generality.
GENERIC_TERMS = frozenset(
    {
        # Pronouns / possessives / question words.
        "she", "her", "hers", "him", "his", "they", "them", "their",
        "theirs", "you", "your", "yours", "mine", "ours", "myself",
        "yourself", "itself", "whose", "whom",
        # Modals / auxiliaries ("can" is a stopword; "cannot" is not).
        "may", "might", "must", "shall", "let", "lets", "cannot",
        # Common verbs: filler actions where only the object is topical.
        "get", "gets", "getting", "got", "give", "gives", "given", "gave",
        "make", "makes", "making", "made", "take", "takes", "taking",
        "took", "taken", "use", "uses", "used", "using", "work", "works",
        "worked", "working", "seem", "seems", "seemed", "look", "looks",
        "looked", "looking", "show", "shows", "showed", "shown",
        "showing", "say", "says", "saying", "said", "see", "sees",
        "seeing", "saw", "seen", "tell", "tells", "told", "ask", "asks",
        "asked", "answer", "answers", "need", "needs", "needed",
        "needing", "want", "wants", "wanted", "try", "tries", "tried",
        "trying", "keep", "keeps", "kept", "keeping", "put", "puts",
        "come", "comes", "coming", "came", "goes", "going", "gone",
        "think", "thinks", "thought", "know", "knows", "known", "knew",
        "believe", "believes", "find", "finds", "found", "happen",
        "happens", "happened", "occur", "occurs", "occurred",
        "continue", "continues", "become", "becomes", "became", "open",
        "opens", "opened", "opening", "close", "closed", "closing",
        "fail", "fails", "failed", "failing", "failure", "failures",
        "run", "runs", "ran", "change", "changes", "changed",
        "changing", "turn", "turns", "turned", "turning", "leave",
        "leaves", "left", "follow", "follows", "followed", "mean",
        "means", "meant", "point", "points", "pointed", "carry",
        "carries", "carried", "cause", "causes", "caused", "review",
        "reviews", "reviewed", "check", "checks", "checked",
        "checking", "delay", "delays", "delayed", "wait", "waits",
        "waiting", "waited", "hold", "contact", "reach", "reaches",
        "reached", "connect", "connects", "connected", "connecting",
        "save", "saves", "saved", "import", "imports", "imported",
        "export", "exports", "exported", "attach", "attached", "detach",
        "detached", "embed", "embeds", "embedded", "insert", "inserts",
        "inserted", "append", "appends", "appended", "prepend", "undo",
        "redo", "register", "registered", "escalate", "escalated",
        "request", "requests", "approve", "approved", "approval",
        "reject", "rejected", "pending", "call", "calls", "called",
        "chat", "chats", "phone", "phones", "mobile", "tablet",
        "notice", "notices", "noticed", "observe", "observed", "watch",
        "watches", "watched", "appear", "appears", "appeared", "copy",
        "ignore", "reveal", "record", "records", "recorded",
        "recording", "report", "reports", "reported",
        # Generic nouns: people, machines, programs, problems, time.
        "user", "users", "client", "clients", "person", "people",
        "agent", "agents", "operator", "operators", "machine",
        "machines", "computer", "computers", "laptop", "laptops",
        "system", "systems", "windows", "microsoft", "program",
        "programs", "application", "applications", "app", "apps",
        "software", "file", "files", "folder", "folders", "error",
        "errors", "issue", "issues", "problem", "problems", "trouble",
        "troubles", "question", "questions", "time", "times", "day",
        "days", "morning", "mornings", "afternoon", "afternoons",
        "today", "tonight", "yesterday", "week", "weeks", "month",
        "months", "year", "years", "date", "dates", "minute",
        "minutes", "hour", "hours", "second", "seconds", "moment",
        "moments", "thing", "things", "something", "anything",
        "nothing", "everything", "stuff", "part", "parts", "set",
        "sets", "box", "boxes", "word", "words", "name", "names",
        "detail", "details", "value", "values", "number", "numbers",
        "data", "input", "example", "examples", "case", "cases", "log", "logs",
        "note", "notes", "summary", "summaries", "guide", "tip",
        "tips", "step", "steps", "order", "pattern", "patterns",
        "table", "pair", "pairs", "tidy", "worth", "guess", "guesses",
        "middle", "end", "ends", "ended", "side", "sides", "hand",
        "hands", "spot", "spots", "trio", "reader", "readers",
        "discussion", "discussions", "handoff", "handoffs", "bucket",
        "buckets", "sign", "signs", "shape", "shapes", "form",
        "forms", "layout", "layouts", "area", "areas", "source",
        "sources", "deep", "deeper", "depth", "letter", "letters",
        "spelling", "team", "company", "companies",
        "organization", "organizations", "org", "department",
        "departments", "office", "offices", "home", "shop", "shops",
        "desk", "desks", "floor", "floors", "building", "buildings",
        "room", "rooms", "post", "posts", "past", "ticket", "tickets",
        "fax", "trial", "trials", "paid", "cost", "costs", "price",
        "type", "types", "kind", "kinds", "sort", "sorts", "category",
        "categories", "class", "classes", "group", "groups", "item",
        "items", "object", "objects", "entity", "entities", "unit",
        "units", "piece", "pieces", "portion", "portions", "page",
        "pages", "character", "characters", "section", "sections",
        "missing", "direct", "directly", "fully", "normal",
        "abnormal", "affected", "outward", "inward", "upward",
        "downward", "consult", "consults", "consulted", "differ",
        "differs", "different", "differently", "quote", "quotes",
        "quoted", "write", "writes", "wrote", "written", "down",
        "visible", "hidden", "behind",
        # Generic adjectives / adverbs / determiners / conjunctions.
        "new", "old", "only", "same", "other", "others", "another",
        "each", "every", "all", "some", "any", "more", "most", "many",
        "much", "few", "several", "various", "couple", "lot", "lots",
        "short", "long", "big", "small", "large", "little", "huge",
        "tiny", "good", "better", "best", "bad", "worse", "worst",
        "always", "never", "often", "sometimes", "usually", "rarely",
        "once", "twice", "first", "second", "third", "last", "next",
        "previous", "current", "currently", "ago", "recent",
        "recently", "already", "yet", "still", "again", "anymore",
        "nowadays", "meanwhile", "eventually", "finally", "initially",
        "originally", "presently", "lately", "also", "even",
        "though", "although", "else", "instead", "otherwise",
        "anyway", "anyhow", "however", "therefore", "thus", "hence",
        "accordingly", "because", "despite", "except", "besides",
        "beyond", "around", "across", "along", "away", "between",
        "within", "among", "upon", "toward", "towards", "against",
        "under", "below", "above", "beneath", "onto", "into",
        "before", "after", "during", "since", "until", "unless", "over",
        "beside", "alongside", "apart", "aside", "together",
        "alone", "about", "via", "etc", "plus", "minus", "versus",
        "well", "back", "forth", "out", "top", "bottom", "upper",
        "lower", "front", "right", "wrong", "correct", "correctly",
        "proper", "properly", "actual", "actually", "real", "really",
        "true", "false", "okay", "done", "ready", "finished",
        "finish", "complete", "completed", "entire", "whole",
        "entirely", "completely", "almost", "nearly", "hardly",
        "barely", "simply", "merely", "exactly", "precisely",
        "roughly", "approximately", "like", "annoying", "weird",
        "strange", "odd", "funny", "broken", "broke", "warranty",
        "specific", "particular", "certain", "typical", "regular",
        "irregular", "random", "intermittent", "sporadic",
        "constant", "constantly", "periodic", "daily", "weekly",
        "monthly", "nightly", "hourly", "general", "common", "rare",
        "uncommon", "full", "empty", "blank", "clear", "clean",
        "dirty", "fresh", "solid", "liquid", "wet", "heavy",
        "strong", "weak", "poor", "rich", "plain", "fancy",
        "simple", "easy", "hard", "difficult", "complex", "basic",
        "advanced", "support", "helpful", "assistance", "kindly",
        "dear", "regards", "sincerely", "respectfully", "thanks",
        "thank", "sorry", "hello", "handbook", "tutorial",
        "lesson", "course", "training", "priority", "urgent",
        "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "zero", "hundred", "thousand",
        "million", "click", "clicks", "clicked", "clicking",
        "fired", "safety", "disregard", "immediately",
    }
)


@dataclass(frozen=True)
class GateVerdict:
    """Explainable keep/drop decision for one ranked passage."""

    passed: bool
    reasons: tuple[str, ...]


def document_frequencies(corpus: LoadedCorpus) -> dict[str, int]:
    """Count, per token, in how many corpus documents it occurs.

    A token counts for a document when it appears in any span token set
    or in the document title / section headings (the same title signal
    ranking uses).
    """
    by_doc: dict[str, set[str]] = {}
    for span in corpus.spans:
        by_doc.setdefault(span.doc_id, set()).update(span.tokens)
    for doc in corpus.documents:
        present = by_doc.setdefault(doc.entry.doc_id, set())
        present.update(
            tokenize(
                f"{doc.entry.title} "
                + " ".join(s.heading for s in doc.sections),
                limit=200,
            )
        )
    counts: dict[str, int] = {}
    for present in by_doc.values():
        for token in present:
            counts[token] = counts.get(token, 0) + 1
    return counts


def is_error_code(token: str) -> bool:
    """True for code-like tokens: 0x-hex or 3+ digit numbers."""
    return bool(_CODE_RE.match(token or ""))


def is_discriminating(term: str, df: dict[str, int]) -> bool:
    """True when a term is rare in the corpus and not generic filler.

    Unknown terms (df 0) default to discriminating: a novel topical
    word must not be silenced just because the seed corpus never saw
    it. In practice judged terms always matched a span, so df >= 1.
    """
    if not term or term in GENERIC_TERMS:
        return False
    return df.get(term, 0) <= MAX_DISCRIMINATING_DF


def judge_passage(
    p_hit: set[str],
    s_hit: set[str],
    e_hit: set[str],
    t_hit: set[str],
    df: dict[str, int],
) -> GateVerdict:
    """Keep/drop one ranked passage, with machine-readable reasons.

    Args mirror the ranking hit sets: problem / service / evidence token
    overlap with the span, plus query overlap with title+heading. ``df``
    comes from :func:`document_frequencies`. Reasons are stable,
    alphabetically sorted ``criterion:term`` strings; a dropped passage
    carries exactly one ``generic-only:...`` reason naming the matched
    filler.
    """
    reasons: list[str] = []
    for token in sorted(set(p_hit) | set(s_hit) | set(e_hit) | set(t_hit)):
        if is_error_code(token):
            reasons.append(f"error-code:{token}")
    for token in sorted(set(t_hit)):
        if is_discriminating(token, df):
            reasons.append(f"subsystem:{token}")
    for token in sorted(set(e_hit)):
        if is_discriminating(token, df):
            reasons.append(f"evidence:{token}")
    # Plain topic overlap needs a coherent pair: one lone rare word is
    # not relevance ("shared" matching a crash note for a sync case).
    topics = sorted(
        token
        for token in set(p_hit) | set(s_hit)
        if is_discriminating(token, df)
    )
    if len(topics) >= 2:
        reasons.extend(f"topic:{token}" for token in topics)
    if reasons:
        return GateVerdict(passed=True, reasons=tuple(sorted(reasons)))
    matched = sorted(set(p_hit) | set(s_hit) | set(e_hit)) or sorted(set(t_hit))
    detail = ",".join(matched[:12])
    return GateVerdict(
        passed=False,
        reasons=(f"generic-only:{detail}" if detail else "generic-only",),
    )
