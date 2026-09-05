"""Symbol table builder -> ``symbols.db`` (SQLite).

Precedence, strict, per specs/02_BACKEND.md #2:

1. ``verifier.symbols`` output, if ``meta.yaml`` defines the command --
   ground truth, ``source='verifier'``.
2. Parsed examples, for toolchains with no symbol dump -- ``source='examples'``.
3. Doc scraping, last resort, lowest trust -- ``source='docs'``.

A tier below the one that is authoritative for a given corpus may only
*enrich* an existing row (``doc_anchor``, ``example_refs``); it may never
introduce a new row for a name the authoritative tier didn't report, and it
may never overwrite ``source`` or any ground-truth field. Concretely: if
``verifier.symbols`` is defined, it alone determines the set of rows in the
table (this is what keeps "52 PLINTH symbols, all source='verifier'" exactly
52 rather than 52 + doc-scraping noise) -- examples/docs may only decorate
those 52 rows. If no ``verifier.symbols`` is defined, examples becomes the
authoritative tier instead, and docs may only decorate its rows.

Corpus-agnostic: nothing here branches on a language name. Whether tier 1 is
usable is a data question (does meta.yaml define verifier.symbols? did the
command run and produce JSON?), never a name check.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from ashlar.config import REPO_ROOT, Config, CorpusMeta

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

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CODE_SPAN_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

# Structural/common words filtered out of the tier-2 example vocabulary scan
# so the fallback isn't dominated by noise. Deliberately small and generic
# (English stopwords, not language keywords) to keep this corpus-agnostic.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "and", "or", "not", "of", "to",
    "in", "on", "for", "with", "this", "that", "it", "as", "at", "by",
}


def _blank_symbol(name: str, source: str) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "unknown",
        "valid_parents": [],
        "valid_children": [],
        "arg_shape": None,
        "dimension": None,
        "required": 0,
        "range_min": None,
        "range_max": None,
        "doc_anchor": None,
        "example_refs": [],
        "source": source,
    }


def run_symbols_command(
    meta: CorpusMeta, cfg: Config, timeout_s: int | None = None
) -> list[dict[str, Any]] | None:
    """Tier 1. Runs the toolchain's own ``symbols`` dump if ``meta.yaml``
    defines one. Returns ``None`` -- never raises -- if undefined, if the
    command fails to launch/times out, or if its stdout isn't the expected
    JSON shape; callers then fall back to tier 2. A ``None`` here means
    "tier 1 unusable", which is different from "tier 1 ran and reported
    zero symbols" (an empty list from a defined, successful command)."""
    if not meta.verifier.symbols:
        return None
    try:
        proc = subprocess.run(
            meta.verifier.symbols,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s or meta.sandbox.timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or "symbols" not in payload:
        return None
    raw_symbols = payload.get("symbols")
    if raw_symbols is None:
        return None

    out = []
    for s in raw_symbols:
        entry = _blank_symbol(s["name"], "verifier")
        entry["kind"] = s.get("kind", "unknown")
        entry["valid_parents"] = s.get("valid_parents", [])
        entry["valid_children"] = s.get("valid_children", [])
        entry["arg_shape"] = s.get("arg_shape")
        entry["dimension"] = s.get("dimension")
        entry["required"] = int(bool(s.get("required", False)))
        entry["range_min"] = s.get("range_min")
        entry["range_max"] = s.get("range_max")
        entry["doc_anchor"] = s.get("doc_anchor")
        entry["example_refs"] = s.get("example_refs", [])
        out.append(entry)
    return out


def collect_example_symbols(meta: CorpusMeta) -> list[dict[str, Any]]:
    """Tier 2. For toolchains with no symbols dump, derive candidate symbols
    from actual usage in the example corpus: the identifier vocabulary,
    with every occurrence recorded as an example_ref. This is a generic
    heuristic, not a real grammar -- a toolchain like COBOL will eventually
    want tree-sitter-cobol / ProLeap for this tier; this keeps the code path
    real and testable in the meantime (specs/02_BACKEND.md #2)."""
    examples_dir = meta.root / "examples"
    if not examples_dir.is_dir():
        return []
    counts: dict[str, int] = {}
    refs: dict[str, list[dict[str, Any]]] = {}
    for f in sorted(p for p in examples_dir.glob("*") if p.is_file()):
        rel = f.relative_to(meta.root).as_posix()
        for lineno, line in enumerate(f.read_text().splitlines(), start=1):
            for m in IDENT_RE.finditer(line):
                tok = m.group(0)
                if tok.lower() in _STOPWORDS:
                    continue
                counts[tok] = counts.get(tok, 0) + 1
                bucket = refs.setdefault(tok, [])
                if len(bucket) < 20:
                    bucket.append({"file": rel, "line": lineno})
    out = []
    for name in counts:
        entry = _blank_symbol(name, "examples")
        entry["kind"] = "identifier"
        entry["example_refs"] = refs.get(name, [])
        out.append(entry)
    return out


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    return re.sub(r"\s+", "-", slug.strip())


def collect_doc_symbols(meta: CorpusMeta) -> list[dict[str, Any]]:
    """Tier 3, lowest trust. Scrapes inline code spans (`` `word` ``) out of
    the docs as candidate symbol names, anchored to the nearest preceding
    heading. Generic across any markdown corpus -- no language-specific
    parsing."""
    docs_dir = meta.root / "docs"
    if not docs_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in sorted(p for p in docs_dir.glob("**/*") if p.is_file()):
        rel = f.relative_to(meta.root).as_posix()
        current_heading: str | None = None
        for line in f.read_text().splitlines():
            hm = HEADING_RE.match(line)
            if hm:
                current_heading = hm.group(2).strip()
                continue
            for m in CODE_SPAN_RE.finditer(line):
                name = m.group(1)
                if name in seen:
                    continue
                seen.add(name)
                anchor = f"{rel}#{_slugify(current_heading)}" if current_heading else rel
                entry = _blank_symbol(name, "docs")
                entry["kind"] = "identifier"
                entry["doc_anchor"] = anchor
                out.append(entry)
    return out


def _merge_refs(
    existing: list[dict[str, Any]] | None, new: list[dict[str, Any]] | None, cap: int = 50
) -> list[dict[str, Any]]:
    existing = existing or []
    new = new or []
    seen = {(r["file"], r["line"]) for r in existing}
    merged = list(existing)
    for r in new:
        key = (r["file"], r["line"])
        if key not in seen:
            seen.add(key)
            merged.append(r)
    return merged[:cap]


def merge_symbol_tiers(
    verifier_symbols: list[dict[str, Any]] | None,
    example_symbols: list[dict[str, Any]],
    doc_symbols: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge the three tiers into name -> row. Exactly one tier is
    authoritative (may introduce new rows); every other tier may only
    enrich rows already present. See module docstring for why."""
    if verifier_symbols is not None:
        authoritative, enrich_tiers = verifier_symbols, [example_symbols, doc_symbols]
    elif example_symbols:
        authoritative, enrich_tiers = example_symbols, [doc_symbols]
    else:
        authoritative, enrich_tiers = doc_symbols, []

    table: dict[str, dict[str, Any]] = {e["name"]: dict(e) for e in authoritative}
    for tier in enrich_tiers:
        for e in tier:
            existing = table.get(e["name"])
            if existing is None:
                continue  # enrichment-only tier: never introduces a new row
            if existing.get("doc_anchor") is None and e.get("doc_anchor"):
                existing["doc_anchor"] = e["doc_anchor"]
            existing["example_refs"] = _merge_refs(existing.get("example_refs"), e.get("example_refs"))
    return table


def write_symbols_db(db_path: Path, table: dict[str, dict[str, Any]]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM symbols")
        conn.execute("DELETE FROM example_index")
        for row in table.values():
            conn.execute(
                "INSERT INTO symbols (name, kind, valid_parents, valid_children, arg_shape, "
                "dimension, required, range_min, range_max, doc_anchor, example_refs, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["name"],
                    row["kind"],
                    json.dumps(row.get("valid_parents") or []),
                    json.dumps(row.get("valid_children") or []),
                    row.get("arg_shape"),
                    row.get("dimension"),
                    int(bool(row.get("required", False))),
                    row.get("range_min"),
                    row.get("range_max"),
                    row.get("doc_anchor"),
                    json.dumps(row.get("example_refs") or []),
                    row["source"],
                ),
            )
            for ref in row.get("example_refs") or []:
                line = ref["line"]
                conn.execute(
                    "INSERT INTO example_index (symbol, file, line, snippet_start, snippet_end) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (row["name"], ref["file"], line, max(1, line - 2), line + 2),
                )
        conn.commit()
    finally:
        conn.close()


def build_symbol_table(meta: CorpusMeta, cfg: Config, db_path: Path) -> dict[str, Any]:
    """Build (or replace) ``symbols.db`` at ``db_path``. Returns
    ``{"total": int, "by_source": {"verifier": n, "examples": n, "docs": n}}``
    for the ingest manifest."""
    verifier_symbols = run_symbols_command(meta, cfg)
    example_symbols = collect_example_symbols(meta)
    doc_symbols = collect_doc_symbols(meta)

    table = merge_symbol_tiers(verifier_symbols, example_symbols, doc_symbols)
    write_symbols_db(db_path, table)

    by_source: dict[str, int] = {}
    for row in table.values():
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    return {"total": len(table), "by_source": by_source}
