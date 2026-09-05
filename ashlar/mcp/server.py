"""The five MCP tools, over stdio. Signatures and return shapes are fixed by
``specs/00_ARCHITECTURE.md`` #6 -- implemented exactly, not improvised.

Ollama never talks to this process. The harness is the wire
(00_ARCHITECTURE.md #2); this server only ever talks to whichever process
embeds it over stdio JSON-RPC.

No tool here ever raises to the model: every tool wraps its body in
try/except and returns ``{"error": "<message>"}`` on failure, per
specs/02_BACKEND.md #3. Corpus-agnostic: the only per-corpus state is
``_meta``/``_cfg``, loaded once from ``config.yaml`` -- nothing branches on
a language name.

**Do not add a sixth tool.** See 00_ARCHITECTURE.md #7: these are generic
primitives parameterized by argument; coverage scales in the corpus data,
not in code.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ashlar.config import Config, CorpusMeta, load_config, load_corpus_meta
from ashlar.mcp.sandbox import run_verifier

mcp = FastMCP("ashlar")

# Bound at import time to whichever corpus config.yaml names, and
# re-pointable live via set_active_corpus() -- this is what lets
# `POST /corpus/switch` (03_HARNESS.md #5) change every tool below without a
# process restart. Corpus-agnostic: nothing here branches on a language
# name, only on this state.
_cfg: Config = load_config()
_meta: CorpusMeta = load_corpus_meta(_cfg.corpus)

CONTEXT_LINES = 1
MAX_READ_LINES = 2000
VALID_GREP_KINDS = ("all", "doc", "example", "cache")


def set_active_corpus(name: str) -> CorpusMeta:
    """Re-point every tool at a different corpus, in place. `name` is the
    name of any folder under `corpora/`."""
    global _cfg, _meta
    import dataclasses

    _cfg = dataclasses.replace(_cfg, corpus=name)
    _meta = load_corpus_meta(name)
    return _meta


def _corpus_root() -> Path:
    return _meta.root


def _symbols_db_path() -> Path:
    return _meta.root / ".index" / "symbols.db"


def _connect_symbols_db() -> sqlite3.Connection | None:
    """None if ingest hasn't been run yet for this corpus -- callers turn
    that into a `{"error": ...}` response, never a crash."""
    db_path = _symbols_db_path()
    if not db_path.exists():
        return None
    return sqlite3.connect(str(db_path))


# ---------------------------------------------------------------------------
# lookup_symbol
# ---------------------------------------------------------------------------


@mcp.tool()
def lookup_symbol(name: str) -> dict[str, Any]:
    """Confirm a symbol exists and where it is legal. Call this before
    emitting any identifier you are not certain about. Returns valid parent
    blocks, argument shape, required units, and real usage locations. If
    the symbol is unknown, `found` is false in the response -- do not guess
    and emit it anyway; try `grep_corpus` instead."""
    try:
        conn = _connect_symbols_db()
        if conn is None:
            return {"error": "symbol table not built yet -- run python -m ashlar.ingest first"}
        try:
            row = conn.execute(
                "SELECT name, kind, valid_parents, valid_children, arg_shape, dimension, "
                "required, doc_anchor, example_refs, source FROM symbols WHERE name = ?",
                (name,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return {"found": False, "name": name}

        (
            row_name,
            kind,
            valid_parents,
            valid_children,
            arg_shape,
            dimension,
            required,
            doc_anchor,
            example_refs,
            source,
        ) = row
        return {
            "found": True,
            "name": row_name,
            "kind": kind,
            "valid_parents": json.loads(valid_parents) if valid_parents else [],
            "valid_children": json.loads(valid_children) if valid_children else [],
            "arg_shape": arg_shape,
            "dimension": dimension,
            "required": bool(required),
            "doc_anchor": doc_anchor,
            "example_refs": json.loads(example_refs) if example_refs else [],
            "source": source,
        }
    except Exception as exc:  # never raise to the model
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# grep_corpus
# ---------------------------------------------------------------------------


def _iter_searchable_files(kind: str) -> list[tuple[str, Path]]:
    """(kind, path) pairs for regex search: examples flat, then docs
    recursively (specs/02_BACKEND.md #1). Never includes pairs/.

    Examples come first deliberately, not alphabetically: `grep_corpus`
    stops as soon as it hits `limit`, and a broad keyword alternation
    (common structural words like "define"/"platform" are legal keywords
    too, so they end up in almost every prompt's pattern) can produce many
    matches in docs alone -- easily enough to exhaust a limit of 12 before
    a single example file is even opened. Found via Phase 2 live-model
    diagnosis: a real task's pre-fetch returned 12/12 hits from
    docs/errors.md and zero from examples/, even though the relevant
    example file matched on other keywords in the same query. That
    inverts `prompts/system.md`'s own instruction ("prefer imitating a
    real example over reasoning from prose documentation") at the
    retrieval layer, before the model ever sees anything."""
    out: list[tuple[str, Path]] = []
    if kind in ("all", "example"):
        examples_dir = _corpus_root() / "examples"
        if examples_dir.is_dir():
            out.extend(("example", p) for p in sorted(examples_dir.glob("*")) if p.is_file())
    if kind in ("all", "doc"):
        docs_dir = _corpus_root() / "docs"
        if docs_dir.is_dir():
            out.extend(("doc", p) for p in sorted(docs_dir.glob("**/*")) if p.is_file())
    return out


def _cache_entries() -> list[dict[str, str]]:
    """``verified_cache`` rows, exposed as kind='cache' search targets
    (specs/02_BACKEND.md #5), restricted to ``behavioral=1`` rows only.

    Real bug, found live and fixed: this used to expose *every* cached row,
    on the premise that "every compile-clean solution the harness writes
    back is retrievable." But "compile-clean" only means `verify(run=True)`
    found no runtime error -- for a task with no observable output (a bare
    SET, no WRITE), that's trivially true even for structurally wrong code,
    since there's nothing in an empty stdout for error-extraction to catch.
    A bad-but-error-free row cited as a "real example" to the next similar
    prompt reproduced the same mistake, which was then *also* cached,
    confirmed live as a genuine self-reinforcing corruption loop (see
    `ashlar/harness/memory.py`'s schema comment for the full story). Only
    rows that were actually checked against real expected output
    (`corpora/<name>/pairs/*/expected.txt`) and matched are safe to hold up
    as ground truth to a different prompt -- `cache_lookup`'s own
    exact/near-repeat serving path is unaffected by this filter and still
    considers every row, since re-serving your own past answer to the
    identical prompt (always re-verified before being returned) carries no
    extra risk."""
    conn = _connect_symbols_db()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT key, source FROM verified_cache WHERE behavioral = 1"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [{"file": f"cache:{key}", "text": source or ""} for key, source in rows]


def _grep_lines(file_label: str, file_kind: str, lines: list[str], regex: re.Pattern) -> list[dict]:
    hits = []
    for i, line in enumerate(lines):
        if regex.search(line):
            hits.append(
                {
                    "file": file_label,
                    "line": i + 1,
                    "text": line,
                    "context_before": [lines[i - 1]] if i > 0 else [],
                    "context_after": [lines[i + 1]] if i + 1 < len(lines) else [],
                    "kind": file_kind,
                }
            )
    return hits


@mcp.tool()
def grep_corpus(pattern: str, limit: int = 20, kind: str = "all") -> list[dict[str, Any]] | dict[str, Any]:
    """Regex search across documentation and example source. kind is one of
    all|doc|example|cache. Returns file, line, matching text, and
    surrounding context lines. Use this to check real usage before
    inventing syntax -- most questions ("how is X spelled", "does Y take an
    argument") are answered by a well-chosen pattern here, not by asking
    for a new tool."""
    try:
        if kind not in VALID_GREP_KINDS:
            return {"error": f"invalid kind: {kind!r}, expected one of {VALID_GREP_KINDS}"}
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return {"error": f"invalid pattern: {exc}"}

        results: list[dict[str, Any]] = []

        for file_kind, path in _iter_searchable_files(kind):
            rel = path.relative_to(_corpus_root()).as_posix()
            lines = path.read_text().splitlines()
            for hit in _grep_lines(rel, file_kind, lines, regex):
                results.append(hit)
                if len(results) >= limit:
                    return results

        if kind in ("all", "cache"):
            for entry in _cache_entries():
                cache_lines = entry["text"].splitlines()
                for hit in _grep_lines(entry["file"], "cache", cache_lines, regex):
                    results.append(hit)
                    if len(results) >= limit:
                        return results

        return results
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# get_examples
# ---------------------------------------------------------------------------


@mcp.tool()
def get_examples(symbol: str, n: int = 3) -> list[dict[str, Any]] | dict[str, Any]:
    """Return real, verified usages of a symbol from the example corpus.
    Prefer this over reasoning from documentation alone -- a real program
    that already compiles is stronger evidence than a paragraph of prose,
    and shows the surrounding syntax you'd otherwise have to guess."""
    try:
        conn = _connect_symbols_db()
        if conn is None:
            return {"error": "symbol table not built yet -- run python -m ashlar.ingest first"}
        try:
            rows = conn.execute(
                "SELECT file, snippet_start, snippet_end FROM example_index "
                "WHERE symbol = ? ORDER BY rowid LIMIT ?",
                (symbol, max(n, 0)),
            ).fetchall()
        finally:
            conn.close()

        root = _corpus_root().resolve()
        out: list[dict[str, Any]] = []
        for file_rel, snippet_start, snippet_end in rows:
            full_path = (root / file_rel).resolve()
            try:
                full_path.relative_to(root)
            except ValueError:
                continue  # defensive: never read outside the corpus root
            if not full_path.is_file():
                continue
            lines = full_path.read_text().splitlines()
            s = max(1, snippet_start)
            e = min(len(lines), snippet_end)
            text = "\n".join(lines[s - 1 : e])
            out.append({"file": file_rel, "start": s, "end": e, "text": text, "verified": True})
        return out
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


@mcp.tool()
def read_file(path: str, start: int = 1, end: int = -1) -> dict[str, Any]:
    """Read a line range from a corpus file. Paths are relative to the
    corpus root and are confined to it -- a traversal attempt (e.g.
    `../../etc/passwd`) returns `{"error": ...}`, never a read. Use this to
    pull up full context around something `grep_corpus` or `get_examples`
    pointed you at."""
    try:
        root = _corpus_root().resolve()
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return {"error": f"path {path!r} escapes the corpus root"}
        if not candidate.is_file():
            return {"error": f"no such file: {path}"}

        lines = candidate.read_text().splitlines()
        total = len(lines)
        start = max(1, start)
        end = total if end == -1 else min(end, total)

        if end < start:
            return {"file": path, "start": start, "end": end, "text": "", "truncated": False}

        truncated = False
        if end - start + 1 > MAX_READ_LINES:
            end = start + MAX_READ_LINES - 1
            truncated = True

        text = "\n".join(lines[start - 1 : end])
        return {"file": path, "start": start, "end": end, "text": text, "truncated": truncated}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


@mcp.tool()
def verify(source: str, run: bool = False, stdin: str = "") -> dict[str, Any]:
    """Compile or parse candidate source in an offline sandbox, optionally
    executing it. Never return code to the user that has not passed this.
    Returns ok plus a list of errors with line numbers and codes."""
    try:
        mode = "run" if run else "parse"
        return run_verifier(source, mode, stdin=stdin, meta=_meta, cfg=_cfg)
    except Exception as exc:  # e.g. container sandbox mode's NotImplementedError
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run()
