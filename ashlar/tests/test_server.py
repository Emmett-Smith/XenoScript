"""Exercises all five MCP tools by calling the underlying functions
directly (the @mcp.tool() decorator from mcp.server.fastmcp.FastMCP leaves
the function itself a plain, directly-callable Python function -- verified
interactively; see the backend session report). This runs the exact same
code path a real stdio MCP session would invoke, so a full MCP-inspector
session was not additionally run for these tests.

Ingest is run once per test session (against the real corpora/stub) so
symbols.db / example_index / the doc+example files on disk are guaranteed
to exist and be current, regardless of ingest artifacts being gitignored.
"""

import pytest

from ashlar.ingest.pipeline import run_ingest
from ashlar.mcp import server


@pytest.fixture(scope="module", autouse=True)
def _ingested_stub_corpus():
    run_ingest("corpora/stub")


# ---------------------------------------------------------------------------
# lookup_symbol
# ---------------------------------------------------------------------------


def test_lookup_symbol_not_found_shape():
    result = server.lookup_symbol("definitely_not_a_real_symbol")
    assert result == {"found": False, "name": "definitely_not_a_real_symbol"}


def test_lookup_symbol_found_when_present(tmp_path, monkeypatch):
    # stub's verifier.symbols reports zero symbols, so exercise the "found"
    # branch by pointing the module at a hand-built symbols.db.
    import json

    from ashlar.config import (
        CorpusMeta,
        CorpusSandbox,
        RetrievalConfig,
        VerifierCommands,
        load_config,
    )
    from ashlar.ingest.symbols import build_symbol_table

    fixture_root = tmp_path / "fixture_corpus"
    fixture_root.mkdir()

    dump_script = tmp_path / "symbols_dump.py"
    payload = {
        "symbols": [
            {
                "name": "altitude",
                "kind": "attribute",
                "valid_parents": ["platform"],
                "arg_shape": "<number:length>",
                "dimension": "length",
                "required": True,
            }
        ]
    }
    # Double-encode so JSON's true/false/null never get embedded as raw
    # (invalid) Python source -- see the identical helper in test_symbols.py.
    dump_script.write_text(f"print({json.dumps(json.dumps(payload))})\n")

    meta = CorpusMeta(
        language="fixture",
        display_name="Fixture",
        extension=".fix",
        comment_prefix="#",
        verifier=VerifierCommands(
            parse=["true"], run=["true"], symbols=["python3", str(dump_script)]
        ),
        sandbox=CorpusSandbox(mode="subprocess", timeout_s=5, memory_mb=512),
        retrieval=RetrievalConfig(),
        root=fixture_root,
    )
    build_symbol_table(meta, load_config(), fixture_root / ".index" / "symbols.db")

    monkeypatch.setattr(server, "_meta", meta)
    result = server.lookup_symbol("altitude")
    assert result["found"] is True
    assert result["kind"] == "attribute"
    assert result["valid_parents"] == ["platform"]
    assert result["source"] == "verifier"
    assert result["required"] is True


def test_lookup_symbol_never_raises_returns_error_dict(monkeypatch):
    def boom():
        raise RuntimeError("db is on fire")

    monkeypatch.setattr(server, "_connect_symbols_db", boom)
    result = server.lookup_symbol("altitude")
    assert "error" in result


# ---------------------------------------------------------------------------
# grep_corpus
# ---------------------------------------------------------------------------


def test_grep_corpus_finds_example_hit_with_context():
    results = server.grep_corpus("noise_floor", limit=5, kind="example")
    assert isinstance(results, list)
    assert results, "expected at least one example hit for noise_floor"
    hit = results[0]
    assert hit["kind"] == "example"
    assert "noise_floor" in hit["text"]
    assert set(hit.keys()) == {"file", "line", "text", "context_before", "context_after", "kind"}


def test_grep_corpus_finds_doc_hit():
    results = server.grep_corpus("noise_floor", limit=5, kind="doc")
    assert any(r["kind"] == "doc" for r in results)


def test_grep_corpus_invalid_regex_returns_error_dict_not_exception():
    result = server.grep_corpus("(unclosed[", limit=5)
    assert isinstance(result, dict)
    assert "error" in result
    assert "invalid pattern" in result["error"]


def test_grep_corpus_invalid_kind_returns_error_dict():
    result = server.grep_corpus("noise_floor", kind="not_a_real_kind")
    assert isinstance(result, dict)
    assert "error" in result


def test_grep_corpus_respects_limit():
    results = server.grep_corpus("platform", limit=1, kind="example")
    assert len(results) <= 1


# ---------------------------------------------------------------------------
# get_examples
# ---------------------------------------------------------------------------


def test_get_examples_returns_verified_usages(tmp_path, monkeypatch):
    # Build example_index rows by hand against the real stub examples dir,
    # since stub's verifier.symbols reports 0 symbols (so the real ingest
    # run doesn't populate example_index for "noise_floor" itself).
    import sqlite3

    from ashlar.config import corpus_dir

    db_path = corpus_dir("stub") / ".index" / "symbols.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO example_index (symbol, file, line, snippet_start, snippet_end) "
        "VALUES (?, ?, ?, ?, ?)",
        ("noise_floor", "examples/basic.stub", 2, 1, 3),
    )
    conn.commit()
    conn.close()

    results = server.get_examples("noise_floor", n=3)
    assert isinstance(results, list)
    assert len(results) == 1
    ex = results[0]
    assert ex["file"] == "examples/basic.stub"
    assert ex["verified"] is True
    assert "noise_floor" in ex["text"]


def test_get_examples_unknown_symbol_returns_empty_list():
    assert server.get_examples("no_such_symbol_anywhere", n=3) == []


def test_get_examples_never_raises_returns_error_dict(monkeypatch):
    def boom():
        raise RuntimeError("db is on fire")

    monkeypatch.setattr(server, "_connect_symbols_db", boom)
    result = server.get_examples("noise_floor")
    assert isinstance(result, dict)
    assert "error" in result


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


def test_read_file_reads_a_line_range():
    result = server.read_file("examples/basic.stub", 1, 2)
    assert result["file"] == "examples/basic.stub"
    assert result["start"] == 1
    assert result["end"] == 2
    assert "platform demo" in result["text"]
    assert result["truncated"] is False


def test_read_file_default_end_reads_whole_file():
    result = server.read_file("examples/basic.stub")
    assert "end_platform" in result["text"]


def test_read_file_path_traversal_returns_error_never_reads(tmp_path):
    result = server.read_file("../../etc/passwd")
    assert "error" in result

    result2 = server.read_file("../../../../../../etc/passwd", 1, 5)
    assert "error" in result2


def test_read_file_absolute_path_escape_returns_error():
    result = server.read_file("/etc/passwd")
    assert "error" in result


def test_read_file_missing_file_returns_error():
    result = server.read_file("examples/does_not_exist.stub")
    assert "error" in result


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def test_verify_parse_ok():
    result = server.verify("hello world\n")
    assert result["ok"] is True
    assert result["errors"] == []


def test_verify_parse_reports_fail_literal():
    result = server.verify("line one\nline two\nFAIL here\n")
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E041"


def test_verify_run_mode():
    result = server.verify("hello world\n", run=True)
    assert result["ok"] is True
    assert result["stdout"] == "stub run ok\n"


def test_verify_never_raises_returns_error_dict(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("sandbox exploded")

    monkeypatch.setattr(server, "run_verifier", boom)
    result = server.verify("hello")
    assert "error" in result
