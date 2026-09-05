"""Verified snippet cache + failure memory.

00_ARCHITECTURE.md #11 / 03_HARNESS.md #4: two data-only mechanisms, no
weight updates. Writes `symbols.db`'s `verified_cache` and `failures`
tables.

Schema ownership note: `02_BACKEND.md` #2 owns `symbols.db`'s schema
(`ashlar/ingest/symbols.py`, built concurrently in another worktree
tonight). The `CREATE TABLE IF NOT EXISTS` statements below are copied
verbatim from that spec section so this module's own tests have a database
to run against without needing the backend's ingest code importable. If the
backend agent's actual DDL drifts from this (unlikely -- it's copy-pasted),
Phase 2 integration reconciles it; note the drift there, not here.

Hard invariant, tested below: cache_lookup() returning a hit is not itself
permission to serve unverified source. Every caller (see loop.py) must
re-run verify() on the cached source before returning it to the user. This
module cannot enforce that by itself (verification is a `ToolClient`
concern, out of memory.py's scope) -- the invariant is enforced and tested
at the loop level.
"""

from __future__ import annotations

import difflib
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Verbatim from 02_BACKEND.md #2.
SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
  name           TEXT PRIMARY KEY,
  kind           TEXT NOT NULL,
  valid_parents  TEXT,
  valid_children TEXT,
  arg_shape      TEXT,
  dimension      TEXT,
  required       INTEGER DEFAULT 0,
  range_min      REAL,
  range_max      REAL,
  doc_anchor     TEXT,
  example_refs   TEXT,
  source         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kind ON symbols(kind);

CREATE TABLE IF NOT EXISTS example_index (
  symbol TEXT, file TEXT, line INTEGER, snippet_start INTEGER, snippet_end INTEGER
);

CREATE TABLE IF NOT EXISTS failures (
  id INTEGER PRIMARY KEY, code TEXT, message TEXT,
  before_src TEXT, after_src TEXT, resolved INTEGER, ts TEXT
);

CREATE TABLE IF NOT EXISTS verified_cache (
  key TEXT PRIMARY KEY,
  task TEXT, source TEXT, iterations INTEGER, ts TEXT
);
"""

# Near-match similarity floor. Chosen for tonight per 03_HARNESS.md #4's
# explicit allowance ("even simple substring/fuzzy similarity ... is
# acceptable"): difflib.SequenceMatcher ratio over normalized task text, no
# extra dependency, good enough to catch near-duplicate phrasing of the same
# task. A real BM25-over-cached-tasks index is the natural upgrade once the
# backend's indexer is wired in (same corpus BM25 index, kind='cache' rows
# per 02_BACKEND.md #5).
#
# Real bug, found live: 0.82 is too permissive. Two prompts asking to create
# *different* patients ("...patient number 21 storing TESTPERSON,RUN1^33^M"
# vs "...patient number 30 storing WILSON,TOM^52^M") score 0.869 -- the long
# shared sentence scaffolding dominates the ratio even though the actual
# data differs completely -- so the cache silently served patient 21's
# source for a prompt about patient 30. Genuine same-task rephrasing (typo,
# "add" vs "create", added "please") measured 0.94-0.97 on the same prompt.
# Raised the floor above the collision case and below the rephrasing case.
SIMILARITY_FLOOR = 0.93

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")
_DIGITS_RE = re.compile(r"\d+")


def normalize_task(text: str) -> str:
    text = text.lower()
    text = _PUNCT_RE.sub("", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def cache_key(text: str) -> str:
    import hashlib

    return hashlib.sha256(normalize_task(text).encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    key: str
    task: str
    source: str
    iterations: int


class Memory:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(SCHEMA)
            con.commit()
        finally:
            con.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def cache_lookup(self, prompt: str) -> CacheEntry | None:
        key = cache_key(prompt)
        con = self._connect()
        try:
            row = con.execute(
                "SELECT key, task, source, iterations FROM verified_cache WHERE key = ?", (key,)
            ).fetchone()
            if row:
                return CacheEntry(*row)

            norm_prompt = normalize_task(prompt)
            prompt_digits = _DIGITS_RE.findall(norm_prompt)
            best: tuple | None = None
            best_score = 0.0
            for row in con.execute("SELECT key, task, source, iterations FROM verified_cache"):
                candidate_norm = normalize_task(row[1])
                # Hard disqualifier, checked before the fuzzy ratio: numeric
                # literals (patient IDs, quantities, ...) are the most common
                # real differentiator between two instances of the same task
                # template. Two prompts that share almost every word but
                # reference different numbers are different tasks, no matter
                # how high the overall text-similarity ratio comes out.
                if prompt_digits != _DIGITS_RE.findall(candidate_norm):
                    continue
                score = difflib.SequenceMatcher(None, norm_prompt, candidate_norm).ratio()
                if score > best_score:
                    best_score, best = score, row
            if best is not None and best_score >= SIMILARITY_FLOOR:
                return CacheEntry(*best)
            return None
        finally:
            con.close()

    def record_success(self, prompt: str, source: str, iterations: int) -> None:
        key = cache_key(prompt)
        con = self._connect()
        try:
            con.execute(
                "INSERT OR REPLACE INTO verified_cache (key, task, source, iterations, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, prompt, source, iterations, _now_iso()),
            )
            con.commit()
        finally:
            con.close()

    def record_failure(self, prompt: str, history: list[Any]) -> None:
        """`history` is the loop's list of `HistoryTurn`s (see repair.py) for
        the failed task. Logs one `failures` row per (turn, error) so
        `top_failures` can be a plain GROUP BY over error codes."""
        con = self._connect()
        try:
            for turn in history:
                errors = getattr(turn, "errors", None) or []
                before_src = getattr(turn, "source", None)
                if not errors:
                    con.execute(
                        "INSERT INTO failures (code, message, before_src, after_src, resolved, ts) "
                        "VALUES (?, ?, ?, ?, 0, ?)",
                        (None, f"unresolved: {prompt}", before_src, None, _now_iso()),
                    )
                    continue
                for err in errors:
                    con.execute(
                        "INSERT INTO failures (code, message, before_src, after_src, resolved, ts) "
                        "VALUES (?, ?, ?, ?, 0, ?)",
                        (err.get("code"), err.get("message"), before_src, None, _now_iso()),
                    )
            con.commit()
        finally:
            con.close()

    def top_failures(self, n: int = 5) -> list[str]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT code, COUNT(*) AS c FROM failures WHERE code IS NOT NULL "
                "GROUP BY code ORDER BY c DESC LIMIT ?",
                (n,),
            ).fetchall()
            return [f"{code} ({count}x)" for code, count in rows]
        finally:
            con.close()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
