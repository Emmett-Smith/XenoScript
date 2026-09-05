import pytest

from ashlar.config import (
    CorpusMeta,
    CorpusSandbox,
    RetrievalConfig,
    VerifierCommands,
    load_config,
    load_corpus_meta,
)
from ashlar.mcp.sandbox import run_verifier


def _fake_meta(tmp_path, parse_cmd, timeout_s=10, mode="subprocess", extension=".stub"):
    return CorpusMeta(
        language="fixture",
        display_name="Fixture",
        extension=extension,
        comment_prefix="#",
        verifier=VerifierCommands(parse=parse_cmd, run=parse_cmd, symbols=None),
        sandbox=CorpusSandbox(image=None, timeout_s=timeout_s, memory_mb=512, mode=mode),
        retrieval=RetrievalConfig(),
        root=tmp_path,
    )


def test_run_verifier_ok_against_stub_corpus():
    cfg = load_config()
    meta = load_corpus_meta("stub")
    result = run_verifier("hello world\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["exit_code"] == 0


def test_run_verifier_reports_fail_literal_against_stub_corpus():
    cfg = load_config()
    meta = load_corpus_meta("stub")
    result = run_verifier("line one\nline two\nFAIL here\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E041"
    assert result["errors"][0]["line"] == 3


def test_run_verifier_run_mode_against_stub_corpus():
    cfg = load_config()
    meta = load_corpus_meta("stub")
    result = run_verifier("hello world\n", "run", meta=meta, cfg=cfg)
    assert result["ok"] is True
    assert result["stdout"] == "stub run ok\n"


def test_run_verifier_unknown_mode_returns_harness_error():
    cfg = load_config()
    meta = load_corpus_meta("stub")
    result = run_verifier("hello", "explode", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "EHARNESS"


def test_run_verifier_timeout_returns_eharness_and_never_hangs(tmp_path):
    # Fake a slow toolchain: `sleep 5` against a 1s wall-clock cap. Proves
    # the kill-and-return path without needing a real slow verifier.
    cfg = load_config()
    meta = _fake_meta(tmp_path, parse_cmd=["sleep", "5"], timeout_s=1)
    result = run_verifier("anything", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert len(result["errors"]) == 1
    assert result["errors"][0]["code"] == "EHARNESS"
    assert "timed out" in result["errors"][0]["message"]


def test_run_verifier_non_json_stdout_is_eharness_never_silent_pass(tmp_path):
    cfg = load_config()
    # `echo` prints plain text, not JSON -- toolchain misbehavior.
    meta = _fake_meta(tmp_path, parse_cmd=["echo", "not json"])
    result = run_verifier("anything", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "EHARNESS"


def test_run_verifier_derives_ok_from_errors_and_exit_code_not_payload(tmp_path):
    # A misbehaving toolchain claims ok=true but exits nonzero. The sandbox
    # must not trust the payload's own "ok" field.
    cfg = load_config()
    script = tmp_path / "lying.py"
    script.write_text(
        'import json, sys\n'
        'print(json.dumps({"ok": True, "errors": []}))\n'
        'sys.exit(1)\n'
    )
    meta = _fake_meta(tmp_path, parse_cmd=["python3", str(script)])
    result = run_verifier("anything", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["exit_code"] == 1


def test_run_verifier_container_mode_raises_not_implemented(tmp_path):
    cfg = load_config()
    meta = _fake_meta(tmp_path, parse_cmd=["true"], mode="container")
    with pytest.raises(NotImplementedError):
        run_verifier("anything", "parse", meta=meta, cfg=cfg)


def test_run_verifier_command_substitution_uses_file_placeholder(tmp_path):
    # `cat {file}` should echo back exactly what we wrote, proving {file}
    # substitution points at the real candidate file on disk.
    cfg = load_config()
    marker_script = tmp_path / "dump.py"
    marker_script.write_text(
        'import json, sys\n'
        'text = open(sys.argv[1]).read()\n'
        'print(json.dumps({"ok": "MARKER" in text, "errors": []}))\n'
    )
    meta = _fake_meta(tmp_path, parse_cmd=["python3", str(marker_script), "{file}"])
    result = run_verifier("this has MARKER in it\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is True
