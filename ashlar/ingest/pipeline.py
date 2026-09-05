"""Ingest pipeline: chunk docs, index docs+examples with BM25, build the
symbol table, and write ``<corpus>/.index/manifest.json``.

Entry point: ``python -m ashlar.ingest --corpus corpora/<name>``. Corpus-
agnostic by construction -- every per-language behavior comes from
``meta.yaml`` via ``ashlar.config``; this module never branches on a
language name.

``pairs/`` is deliberately only *counted*, never opened: the simplest way to
guarantee ``pairs/*/solution.<ext>`` never enters the BM25 index or symbol
table (specs/02_BACKEND.md #7) is to never read those files at all.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ashlar.config import REPO_ROOT, Config, CorpusMeta, load_config, load_corpus_meta
from ashlar.ingest.chunker import chunk_doc_file
from ashlar.ingest.indexer import build_index
from ashlar.ingest.symbols import build_symbol_table


def _resolve_corpus_name(corpus_arg: str) -> str:
    """Accepts either a bare corpus name ("stub") or a path
    ("corpora/stub", "corpora/stub/") and returns the bare name, since
    ``load_corpus_meta`` wants the former."""
    return Path(corpus_arg.rstrip("/")).name


def _iter_doc_files(meta: CorpusMeta) -> list[Path]:
    docs_dir = meta.root / "docs"
    if not docs_dir.is_dir():
        return []
    return sorted(p for p in docs_dir.glob("**/*") if p.is_file())


def _iter_example_files(meta: CorpusMeta) -> list[Path]:
    examples_dir = meta.root / "examples"
    if not examples_dir.is_dir():
        return []
    return sorted(p for p in examples_dir.glob("*") if p.is_file())


def _iter_pair_dirs(meta: CorpusMeta) -> list[Path]:
    pairs_dir = meta.root / "pairs"
    if not pairs_dir.is_dir():
        return []
    return sorted(p for p in pairs_dir.glob("*") if p.is_dir())


def _symbol_source_label(by_source: dict[str, int], total: int) -> str:
    if total == 0:
        return "none"
    if len(by_source) == 1:
        (only,) = by_source.keys()
        return only
    return "mixed(" + ",".join(f"{k}:{v}" for k, v in sorted(by_source.items())) + ")"


def run_ingest(
    corpus_arg: str, cfg: Config | None = None, meta: CorpusMeta | None = None
) -> dict[str, Any]:
    """Run the full pipeline for one corpus. Returns the manifest dict,
    which is also written to ``<corpus>/.index/manifest.json``.

    ``meta`` is an optional override for tests that need to point at a
    hand-built corpus outside the real ``corpora/`` tree; production
    callers (the CLI) omit it and it is resolved from ``corpus_arg`` via
    ``ashlar.config.load_corpus_meta``.
    """
    cfg = cfg or load_config()
    name = _resolve_corpus_name(corpus_arg)
    meta = meta or load_corpus_meta(name)

    doc_files = _iter_doc_files(meta)
    doc_entries: list[dict[str, Any]] = []
    for f in doc_files:
        rel = f.relative_to(meta.root).as_posix()
        doc_entries.extend(chunk_doc_file(f, rel, meta.retrieval.chunk_strategy))

    example_files = _iter_example_files(meta)
    example_entries: list[dict[str, Any]] = []
    total_example_lines = 0
    for f in example_files:
        rel = f.relative_to(meta.root).as_posix()
        for lineno, line in enumerate(f.read_text().splitlines(), start=1):
            example_entries.append(
                {
                    "kind": "example",
                    "file": rel,
                    "start_line": lineno,
                    "end_line": lineno,
                    "heading_path": None,
                    "text": line,
                }
            )
            total_example_lines += 1

    pair_dirs = _iter_pair_dirs(meta)

    index_dir = meta.root / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)

    all_entries = doc_entries + example_entries
    index = build_index(all_entries, bm25_weight=meta.retrieval.bm25_weight)
    index.save(index_dir / "bm25.pkl")

    with open(index_dir / "chunks.jsonl", "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in all_entries)

    symbol_stats = build_symbol_table(meta, cfg, index_dir / "symbols.db")
    symbol_source = _symbol_source_label(symbol_stats["by_source"], symbol_stats["total"])

    try:
        location = str(index_dir.relative_to(REPO_ROOT))
    except ValueError:
        location = str(index_dir)

    manifest = {
        "language": meta.language,
        "display_name": meta.display_name,
        "docs": {"files": len(doc_files), "chunks": len(doc_entries)},
        "examples": {"files": len(example_files), "lines": total_example_lines},
        "pairs": {"tasks": len(pair_dirs)},
        "symbols": {
            "total": symbol_stats["total"],
            "source": symbol_source,
            "by_source": symbol_stats["by_source"],
        },
        "index": {
            "location": location,
            "files": ["bm25.pkl", "symbols.db", "chunks.jsonl"],
        },
    }

    with open(index_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def format_manifest(manifest: dict[str, Any]) -> str:
    d = manifest["docs"]
    e = manifest["examples"]
    p = manifest["pairs"]
    s = manifest["symbols"]
    idx = manifest["index"]
    lines = [
        f"{manifest['display_name']} ingested",
        f"  docs     {d['files']:>2} files    {d['chunks']:,} chunks",
        f"  examples {e['files']:>2} files      {e['lines']:,} lines indexed",
        f"  pairs    {p['tasks']:>2} tasks",
        f"  symbols  {s['total']} (source: {s['source']})",
        f"  index    {idx['location']}  ({', '.join(idx['files'])})",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ashlar.ingest")
    parser.add_argument(
        "--corpus", required=True, help="corpus name or path, e.g. corpora/<name>"
    )
    args = parser.parse_args(argv)
    manifest = run_ingest(args.corpus)
    print(format_manifest(manifest))


if __name__ == "__main__":
    main()
