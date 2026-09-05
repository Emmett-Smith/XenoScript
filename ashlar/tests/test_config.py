import subprocess
import sys

from ashlar.config import REPO_ROOT, effective_sandbox_mode, load_config, load_corpus_meta


def test_load_config():
    cfg = load_config()
    assert cfg.corpus == "stub"
    assert cfg.model.base_url == "http://localhost:11434/v1"
    assert cfg.harness.max_iter == 4
    assert cfg.sandbox.mode == "subprocess"


def test_load_stub_corpus_meta():
    meta = load_corpus_meta("stub")
    assert meta.language == "stub"
    assert meta.verifier.parse[0] == "python3"
    assert meta.retrieval.bm25_weight == 0.75


def test_effective_sandbox_mode_defaults_to_global():
    cfg = load_config()
    meta = load_corpus_meta("stub")
    assert effective_sandbox_mode(cfg, meta) == "subprocess"


def test_stub_verifier_ok_on_clean_source(tmp_path):
    src = tmp_path / "candidate.stub"
    src.write_text("hello world\n")
    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "corpora/stub/verifier.py"), "parse", str(src)],
        capture_output=True, text=True, check=True,
    )
    import json
    payload = json.loads(out.stdout)
    assert payload["ok"] is True
    assert payload["errors"] == []
    assert payload["exit_code"] == 0


def test_stub_verifier_fails_on_fail_literal(tmp_path):
    src = tmp_path / "candidate.stub"
    src.write_text("line one\nline two\nFAIL here\n")
    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "corpora/stub/verifier.py"), "parse", str(src)],
        capture_output=True, text=True, check=True,
    )
    import json
    payload = json.loads(out.stdout)
    assert payload["ok"] is False
    assert payload["exit_code"] == 1
    assert payload["errors"][0]["code"] == "E041"
    assert payload["errors"][0]["line"] == 3
