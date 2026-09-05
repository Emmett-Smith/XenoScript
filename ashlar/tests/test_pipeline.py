import json
import sqlite3
import time

from ashlar.config import corpus_dir, load_config
from ashlar.ingest.pipeline import run_ingest


def test_run_ingest_against_stub_corpus_is_fast_and_accurate():
    cfg = load_config()
    start = time.monotonic()
    manifest = run_ingest("corpora/stub", cfg=cfg)
    elapsed = time.monotonic() - start
    assert elapsed < 10.0

    assert manifest["docs"]["files"] == 2
    assert manifest["docs"]["chunks"] > 0
    assert manifest["examples"]["files"] == 4
    assert manifest["examples"]["lines"] > 0
    assert manifest["pairs"]["tasks"] == 2

    written = json.loads((corpus_dir("stub") / ".index" / "manifest.json").read_text())
    assert written == manifest


def test_run_ingest_accepts_bare_name_or_path_argument():
    cfg = load_config()
    by_name = run_ingest("stub", cfg=cfg)
    by_path = run_ingest("corpora/stub", cfg=cfg)
    assert by_name["docs"] == by_path["docs"]


def _write_fixture_corpus_with_pairs(corpora_dir):
    """A throwaway corpus, with a pairs/ solution file carrying a marker
    token that must never reach the index or symbol table
    (specs/02_BACKEND.md #7)."""
    (corpora_dir / "docs").mkdir(parents=True)
    (corpora_dir / "examples").mkdir(parents=True)
    (corpora_dir / "pairs" / "001").mkdir(parents=True)
    (corpora_dir / "docs" / "manual.md").write_text("# Manual\nsome doc text\n")
    (corpora_dir / "examples" / "a.fix").write_text("legit_example_line\n")
    (corpora_dir / "pairs" / "001" / "solution.fix").write_text(
        "SECRET_SOLUTION_TOKEN must never be indexed\n"
    )
    (corpora_dir / "meta.yaml").write_text(
        "language: fixture\n"
        "display_name: Fixture\n"
        "extension: .fix\n"
        "comment_prefix: '#'\n"
        "verifier:\n"
        "  parse: ['true']\n"
        "  run: ['true']\n"
        "sandbox:\n"
        "  mode: subprocess\n"
        "  timeout_s: 5\n"
        "retrieval:\n"
        "  bm25_weight: 0.75\n"
        "  chunk_strategy: heading\n"
    )


def test_pairs_solution_files_never_enter_index_or_symbols(tmp_path):
    import ashlar.ingest.pipeline as pipeline_module
    from ashlar.config import (
        ApiConfig,
        Config,
        CorpusMeta,
        CorpusSandbox,
        HarnessConfig,
        ModelConfig,
        RetrievalConfig,
        SandboxConfig,
        VerifierCommands,
    )

    corpora_dir = tmp_path / "corpora" / "fx"
    _write_fixture_corpus_with_pairs(corpora_dir)

    cfg = Config(
        corpus="fx",
        model=ModelConfig(base_url="http://x", name="x", api_key="x", temperature=0.1, max_tokens=10),
        harness=HarnessConfig(),
        sandbox=SandboxConfig(mode="subprocess"),
        api=ApiConfig(),
        raw={},
    )
    meta = CorpusMeta(
        language="fixture",
        display_name="Fixture",
        extension=".fix",
        comment_prefix="#",
        verifier=VerifierCommands(parse=["true"], run=["true"], symbols=None),
        sandbox=CorpusSandbox(mode="subprocess", timeout_s=5, memory_mb=512),
        retrieval=RetrievalConfig(bm25_weight=0.75, embedding_weight=0.25, chunk_strategy="heading"),
        root=corpora_dir,
    )

    manifest = pipeline_module.run_ingest("fx", cfg=cfg, meta=meta)
    assert manifest["pairs"]["tasks"] == 1

    chunks_text = (corpora_dir / ".index" / "chunks.jsonl").read_text()
    assert "SECRET_SOLUTION_TOKEN" not in chunks_text

    manifest_text = json.dumps(manifest)
    assert "SECRET_SOLUTION_TOKEN" not in manifest_text
    # doc+example counts prove the manifest only reflects docs/examples, not pairs
    assert manifest["docs"]["files"] == 1
    assert manifest["examples"]["files"] == 1

    conn = sqlite3.connect(str(corpora_dir / ".index" / "symbols.db"))
    names = {r[0] for r in conn.execute("SELECT name FROM symbols").fetchall()}
    conn.close()
    assert "SECRET_SOLUTION_TOKEN" not in names
