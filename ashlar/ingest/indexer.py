"""BM25 index over doc chunks and example lines.

Corpus-agnostic: the only per-corpus knob this module reads is the BM25
weight from ``meta.yaml``'s ``retrieval.bm25_weight`` -- it never branches on
a language name.

Tokenizer note (see specs/02_BACKEND.md #1, called out as a silent
retrieval-quality killer): underscore identifiers like ``noise_floor`` or
``end_platform`` (PLINTH's convention) must tokenize as one token, not two.
Real second-corpus experience (COBOL) surfaced the same failure mode for a
*different* convention: COBOL's idiomatic identifiers are hyphenated
(``WS-INDEX``, ``CUSTOMER-NAME``), and a bare ``\\w+`` (Python's ``\\w``
excludes ``-``) splits every one of those into two spurious "symbols."
Corpus-agnostic fix: the pattern allows an interior ``-`` as long as a
word character follows it, so a hyphen never becomes its own token and a
trailing/isolated ``-`` (e.g. in ``a - b`` or a bare minus sign before a
number) is never absorbed. Both conventions are asserted explicitly in
ashlar/tests/test_indexer.py -- don't trust the docstring, the tests prove
it.
"""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"\w+(?:-\w+)*")


def tokenize(text: str) -> list[str]:
    """Split text into tokens, preserving underscore- and hyphen-joined
    identifiers as single tokens. Lowercased for case-insensitive matching."""
    return TOKEN_RE.findall(text.lower())


class Bm25Index:
    """A BM25 index over a flat list of entries (doc chunks, example lines,
    and -- once the harness starts writing verified_cache -- cache entries).
    Each entry is a dict with at least {"kind", "file", "text", ...}."""

    def __init__(self, entries: list[dict[str, Any]], bm25_weight: float = 1.0):
        self.entries = entries
        self.bm25_weight = bm25_weight
        corpus = [tokenize(e["text"]) for e in entries]
        self.bm25: BM25Okapi | None = BM25Okapi(corpus) if corpus else None

    def __len__(self) -> int:
        return len(self.entries)

    def search(self, query: str, top_n: int = 10, kind: str = "all") -> list[dict[str, Any]]:
        """Rank entries by BM25 score against ``query``, optionally filtered
        to a single ``kind`` ("doc" | "example" | "cache"). Returns entries
        (plus a "score" field) in descending score order."""
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[dict[str, Any]] = []
        for i in ranked:
            entry = self.entries[i]
            if kind != "all" and entry.get("kind") != kind:
                continue
            # Note: BM25's IDF term can legitimately be 0 (or negative) for
            # very small corpora, e.g. a query term present in every
            # document. That is still a meaningful ranking signal within
            # this corpus, so scores are not filtered by sign here -- only
            # by `kind` and `top_n`.
            out.append({**entry, "score": float(scores[i]) * self.bm25_weight})
            if len(out) >= top_n:
                break
        return out

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {"entries": self.entries, "bm25_weight": self.bm25_weight, "bm25": self.bm25}, f
            )

    @classmethod
    def load(cls, path: Path) -> Bm25Index:
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj = cls.__new__(cls)
        obj.entries = data["entries"]
        obj.bm25_weight = data["bm25_weight"]
        obj.bm25 = data["bm25"]
        return obj


def build_index(entries: list[dict[str, Any]], bm25_weight: float = 1.0) -> Bm25Index:
    return Bm25Index(entries, bm25_weight)
