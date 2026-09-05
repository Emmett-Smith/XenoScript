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
_QUOTED_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")
# Generic identifier pattern: underscore-joined or otherwise word-shaped
# tokens of length >= 3. Corpus-agnostic on purpose -- no language-specific
# specifics live here.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")

_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is",
    "that", "with", "as", "it", "this", "be", "are", "was", "were",
    "write", "make", "create", "define", "add", "set", "using", "use",
}


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
    for tok in lower_tokens:
        if tok in symbol_set:
            add(symbol_set[tok])

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
