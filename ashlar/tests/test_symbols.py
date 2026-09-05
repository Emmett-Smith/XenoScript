import json
import sqlite3

from ashlar.config import CorpusMeta, CorpusSandbox, RetrievalConfig, VerifierCommands, load_config
from ashlar.ingest.symbols import build_symbol_table, merge_symbol_tiers, run_symbols_command


def _meta(tmp_path, symbols_cmd, sandbox_mode="subprocess"):
    return CorpusMeta(
        language="fixture",
        display_name="Fixture",
        extension=".fix",
        comment_prefix="#",
        verifier=VerifierCommands(parse=["true"], run=["true"], symbols=symbols_cmd),
        sandbox=CorpusSandbox(image=None, timeout_s=5, memory_mb=512, mode=sandbox_mode),
        retrieval=RetrievalConfig(),
        root=tmp_path,
    )


def _write_symbols_script(tmp_path, symbols_payload):
    script = tmp_path / "symbols_dump.py"
    script.write_text(
        "import json, sys\n"
        f"print(json.dumps({json.dumps(symbols_payload)}))\n"
    )
    return ["python3", str(script)]


# ---------------------------------------------------------------------------
# Tier 1: verifier.symbols is ground truth
# ---------------------------------------------------------------------------


def test_run_symbols_command_parses_fixture_dump(tmp_path):
    cfg = load_config()
    cmd = _write_symbols_script(
        tmp_path,
        {
            "symbols": [
                {"name": "altitude", "kind": "attribute", "valid_parents": ["platform"]},
                {"name": "platform", "kind": "block"},
            ]
        },
    )
    meta = _meta(tmp_path, cmd)
    result = run_symbols_command(meta, cfg)
    assert result is not None
    names = {s["name"] for s in result}
    assert names == {"altitude", "platform"}
    assert all(s["source"] == "verifier" for s in result)


def test_run_symbols_command_returns_none_when_undefined(tmp_path):
    cfg = load_config()
    meta = _meta(tmp_path, symbols_cmd=None)
    assert run_symbols_command(meta, cfg) is None


def test_run_symbols_command_returns_none_on_bad_json(tmp_path):
    cfg = load_config()
    script = tmp_path / "bad.py"
    script.write_text("print('not json')\n")
    meta = _meta(tmp_path, ["python3", str(script)])
    assert run_symbols_command(meta, cfg) is None


# ---------------------------------------------------------------------------
# Precedence: never let a lower tier overwrite a higher one
# ---------------------------------------------------------------------------


def test_doc_scraped_entry_cannot_clobber_verifier_entry(tmp_path):
    verifier_symbols = [
        {
            "name": "altitude",
            "kind": "attribute",
            "source": "verifier",
            "valid_parents": ["platform"],
            "valid_children": [],
            "arg_shape": "<number:length>",
            "dimension": "length",
            "required": False,
            "range_min": None,
            "range_max": None,
            "doc_anchor": None,
            "example_refs": [],
        }
    ]
    # A doc-scraped entry for the SAME name, disagreeing on kind/arg_shape --
    # this must never win.
    doc_symbols = [
        {
            "name": "altitude",
            "kind": "unknown",
            "source": "docs",
            "doc_anchor": "docs/manual.md#attributes",
            "example_refs": [],
        }
    ]
    table = merge_symbol_tiers(verifier_symbols, [], doc_symbols)
    row = table["altitude"]
    assert row["source"] == "verifier"
    assert row["kind"] == "attribute"  # not clobbered by the doc-scraped "unknown"
    assert row["arg_shape"] == "<number:length>"
    # but it WAS allowed to enrich doc_anchor, since the verifier didn't set one
    assert row["doc_anchor"] == "docs/manual.md#attributes"


def test_verifier_present_means_examples_and_docs_cannot_add_new_rows(tmp_path):
    verifier_symbols = [
        {"name": "altitude", "kind": "attribute", "source": "verifier", "example_refs": [],
         "doc_anchor": None, "valid_parents": [], "valid_children": [], "arg_shape": None,
         "dimension": None, "required": 0, "range_min": None, "range_max": None},
    ]
    example_symbols = [
        {"name": "altitude", "kind": "identifier", "source": "examples",
         "example_refs": [{"file": "examples/a.fix", "line": 3}], "doc_anchor": None},
        {"name": "totally_new_name", "kind": "identifier", "source": "examples",
         "example_refs": [{"file": "examples/a.fix", "line": 4}], "doc_anchor": None},
    ]
    doc_symbols = [
        {"name": "also_new", "kind": "identifier", "source": "docs", "doc_anchor": "docs/x.md"},
    ]
    table = merge_symbol_tiers(verifier_symbols, example_symbols, doc_symbols)
    # exactly the verifier's rows -- no pollution from examples/docs tiers
    assert set(table.keys()) == {"altitude"}
    assert table["altitude"]["source"] == "verifier"
    assert table["altitude"]["example_refs"] == [{"file": "examples/a.fix", "line": 3}]


def test_example_refs_enrichment_merges_and_dedupes(tmp_path):
    verifier_symbols = [
        {"name": "altitude", "kind": "attribute", "source": "verifier",
         "example_refs": [{"file": "examples/a.fix", "line": 1}], "doc_anchor": None,
         "valid_parents": [], "valid_children": [], "arg_shape": None, "dimension": None,
         "required": 0, "range_min": None, "range_max": None},
    ]
    example_symbols = [
        {"name": "altitude", "kind": "identifier", "source": "examples",
         "example_refs": [{"file": "examples/a.fix", "line": 1}, {"file": "examples/b.fix", "line": 7}],
         "doc_anchor": None},
    ]
    table = merge_symbol_tiers(verifier_symbols, example_symbols, [])
    refs = table["altitude"]["example_refs"]
    assert {"file": "examples/a.fix", "line": 1} in refs
    assert {"file": "examples/b.fix", "line": 7} in refs
    assert len(refs) == 2  # the duplicate (a.fix, line 1) was not double-counted


# ---------------------------------------------------------------------------
# Tier 2: no verifier.symbols defined -> examples become authoritative
# (synthetic no-symbols-command corpus, as required by specs/02_BACKEND.md #2)
# ---------------------------------------------------------------------------


def test_build_symbol_table_falls_back_to_examples_when_no_symbols_command(tmp_path):
    cfg = load_config()
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "a.fix").write_text(
        "platform demo\n  noise_floor 10\nend_platform\n"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "manual.md").write_text(
        "# Manual\nThe `noise_floor` attribute controls background level.\n"
    )
    meta = _meta(tmp_path, symbols_cmd=None)
    db_path = tmp_path / ".index" / "symbols.db"
    stats = build_symbol_table(meta, cfg, db_path)

    assert stats["by_source"].get("examples", 0) > 0
    assert "verifier" not in stats["by_source"]

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT source, doc_anchor FROM symbols WHERE name = ?", ("noise_floor",)
    ).fetchone()
    conn.close()
    assert row is not None
    source, doc_anchor = row
    assert source == "examples"
    # docs enriched the examples-derived row with a doc_anchor
    assert doc_anchor is not None


def test_build_symbol_table_with_verifier_writes_exact_rows_to_db(tmp_path):
    cfg = load_config()
    cmd = _write_symbols_script(
        tmp_path,
        {
            "symbols": [
                {"name": "altitude", "kind": "attribute"},
                {"name": "platform", "kind": "block"},
            ]
        },
    )
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "a.fix").write_text("platform demo\n  altitude 10\nend\n")
    meta = _meta(tmp_path, cmd)
    db_path = tmp_path / ".index" / "symbols.db"
    stats = build_symbol_table(meta, cfg, db_path)

    assert stats["total"] == 2
    assert stats["by_source"] == {"verifier": 2}

    conn = sqlite3.connect(str(db_path))
    names = {r[0] for r in conn.execute("SELECT name FROM symbols").fetchall()}
    conn.close()
    assert names == {"altitude", "platform"}
