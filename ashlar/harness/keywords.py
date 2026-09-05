"""`extract_keywords` -- the deterministic retrieval seed.

03_HARNESS.md #1: "Not fancy. Intersect the prompt's tokens with
`symbol_names` from the symbol table, then add any quoted strings and any
tokens matching the language's identifier pattern. Rank symbol-table matches
first. If nothing matches, fall back to the prompt's rarest three tokens by
corpus document frequency."

Integration point for Phase 2: `symbol_names` and `doc_freq` are plain
parameters. Real per-corpus symbol names come from the backend's symbol
table (`ashlar/ingest/symbols.py`, not built in this worktree tonight); a
real corpus document-frequency source comes from the BM25 index
(`ashlar/ingest/indexer.py`, same story). Wiring either in is passing a
different list/callable in -- no change to this function's body.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Deliberately excludes a bare `'` immediately touching a letter on either
# side -- otherwise a contraction anywhere in the prompt ("I've", "can't",
# "it's") gets read as an opening or closing quote, and the "quoted string"
# captured is everything between two unrelated apostrophes, potentially a
# whole multi-sentence span. Found via Phase 2 live-model diagnosis: a real
# task phrased with "I've seen ... even though I can't find it" produced a
# single ~90-character garbage "keyword" spanning both contractions, which
# then dominated the grep_corpus pattern instead of the task's real content.
_QUOTED_RE = re.compile(r"(?<![A-Za-z])'([^'\n]{1,60})'(?![A-Za-z])|\"([^\"\n]{1,60})\"")
# Generic identifier pattern: underscore-joined or otherwise word-shaped
# tokens of length >= 3. Corpus-agnostic on purpose -- no language-specific
# specifics live here.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")

_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is",
    "that", "with", "as", "it", "this", "be", "are", "was", "were",
    "write", "make", "create", "define", "add", "set", "using", "use",
}

# Generic English/software vocabulary clusters, fixed and corpus-agnostic:
# the same clusters apply to every corpus, no matter what it is. Found
# live: a prompt using "outputting" against PLINTH (whose real vocabulary
# for that concept is "trace"/"report", not "output"/"print"/"display")
# got a flat lookup_symbol "not found" and nothing else -- a synonym-
# cluster member has no advantage over any other until it's checked
# against *this* corpus's real symbol_names, so this never hardcodes
# which corpus uses which word.
_SYNONYM_CLUSTERS: tuple[frozenset[str], ...] = (
    frozenset({"output", "print", "display", "show", "write", "emit",
               "log", "report", "trace", "message", "echo"}),
    frozenset({"loop", "repeat", "iterate", "iteration", "cycle",
               "perform", "for", "while", "until", "times"}),
    frozenset({"start", "begin", "init", "initialize", "launch", "spawn",
               "activate"}),
    frozenset({"stop", "end", "halt", "terminate", "finish", "deactivate",
               "abort"}),
    frozenset({"assign", "set", "store", "put", "save", "move", "value"}),
    frozenset({"link", "bind", "reference", "refer", "point", "attach",
               "connect", "mount"}),
    frozenset({"check", "test", "verify", "compare", "condition",
               "conditional", "branch", "decide", "if"}),
    frozenset({"define", "declare", "create", "make", "build",
               "construct", "new"}),
    frozenset({"add", "sum", "increment", "subtract", "decrement",
               "compute", "calculate", "total"}),
)

# Cheap suffix-stripping, not a real stemmer -- just enough to turn common
# gerund/plural/past-tense forms ("outputting", "loops", "activated") into
# something a symbol table or a synonym cluster might actually recognize.
_SUFFIX_STRIPS: tuple[tuple[str, str], ...] = (
    ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("es", ""), ("s", ""),
)


def _stem_candidates(word: str) -> set[str]:
    candidates = {word}
    for suffix, replacement in _SUFFIX_STRIPS:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            candidates.add(word[: -len(suffix)] + replacement)
    return candidates


def _synonym_match(word: str, symbol_set: dict[str, str]) -> str | None:
    """If `word` (or a cheap stem of it) belongs to a synonym cluster, and
    some *other* member of that same cluster is a real symbol in this
    corpus's own table, return that real symbol's canonical-cased name.
    Never invents a symbol; only ever surfaces one that's already real."""
    stems = _stem_candidates(word)
    for cluster in _SYNONYM_CLUSTERS:
        if not stems.isdisjoint(cluster):
            for candidate in cluster:
                if candidate in symbol_set:
                    return symbol_set[candidate]
    return None


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def extract_keywords(
    prompt: str,
    symbol_names: Iterable[str],
    doc_freq: dict[str, int] | Callable[[str], int] | None = None,
    max_keywords: int = 8,
) -> list[str]:
    tokens = _tokenize(prompt)
    lower_tokens = [t.lower() for t in tokens]
    symbol_set = {s.lower(): s for s in symbol_names}

    ranked: list[str] = []
    seen: set[str] = set()

    def add(word: str) -> None:
        key = word.lower()
        if key and key not in seen:
            seen.add(key)
            ranked.append(word)

    # 1. symbol-table matches, ranked first, in prompt order.
    matched_lower: set[str] = set()
    for tok in lower_tokens:
        if tok in symbol_set:
            add(symbol_set[tok])
            matched_lower.add(tok)

    # 1b. a token that didn't match a real symbol directly gets one more
    # chance via a generic synonym/stem cluster before falling through to
    # a raw literal that lookup_symbol is guaranteed to report "not
    # found" for. See _SYNONYM_CLUSTERS above.
    for tok in lower_tokens:
        if tok in matched_lower or tok in _STOPWORDS:
            continue
        resolved = _synonym_match(tok, symbol_set)
        if resolved:
            add(resolved)
            matched_lower.add(tok)

    # 2. quoted strings, verbatim (not lowercased -- may be exact identifiers).
    for m in _QUOTED_RE.finditer(prompt):
        add(m.group(1) or m.group(2))

    # 3. identifier-pattern tokens not already captured, skipping stopwords.
    for tok in tokens:
        if tok.lower() in _STOPWORDS:
            continue
        if _IDENTIFIER_RE.match(tok):
            add(tok)

    if ranked:
        return ranked[:max_keywords]

    # 4. fallback: rarest three tokens by corpus document frequency.
    candidates = [t for t in set(lower_tokens) if t not in _STOPWORDS and len(t) > 1]
    if not candidates:
        return []

    def freq(tok: str) -> int:
        if doc_freq is None:
            # No frequency source wired yet (Phase 1) -- fall back to a
            # length-based proxy for rarity: longer tokens are typically
            # more specific/rarer in a small DSL corpus than short ones.
            return -len(tok)
        if callable(doc_freq):
            return doc_freq(tok)
        return doc_freq.get(tok, 0)

    candidates.sort(key=freq)
    return candidates[:3]


def build_pattern(keywords: list[str]) -> str:
    """Regex alternation over keywords, for `grep_corpus`."""
    return "|".join(re.escape(k) for k in keywords)
