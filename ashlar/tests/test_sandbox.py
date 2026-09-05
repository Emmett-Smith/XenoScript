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


def _fake_meta(
    tmp_path,
    parse_cmd,
    timeout_s=10,
    mode="subprocess",
    extension=".stub",
    output_format="json",
    error_regex=None,
):
    return CorpusMeta(
        language="fixture",
        display_name="Fixture",
        extension=extension,
        comment_prefix="#",
        verifier=VerifierCommands(
            parse=parse_cmd, run=parse_cmd, symbols=None,
            output_format=output_format, error_regex=error_regex,
        ),
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


TEXT_TOOLCHAIN_ERROR_REGEX = r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<severity>\w+):\s*(?P<message>.*)$"


def _fake_text_toolchain(tmp_path):
    """Mimics a linter that -- unlike PLINTH's CLI -- has no --json mode and
    prints plain `file:line: severity: message` to stderr, matching
    02_BACKEND.md #4's stated GnuCOBOL adapter case. Deliberately a
    synthetic fixture, not literally cobol, so this proves the mechanism is
    corpus-agnostic rather than testing one corpus's specific output."""
    script = tmp_path / "textlint.py"
    script.write_text(
        "import sys\n"
        "text = open(sys.argv[1]).read()\n"
        "if 'BAD' in text:\n"
        "    sys.stderr.write('candidate.fixture:3: error: bad thing found\\n')\n"
        "    sys.stderr.write('candidate.fixture:5: warning: minor issue\\n')\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    return ["python3", str(script), "{file}"]


def test_run_verifier_text_mode_parses_plain_text_errors(tmp_path):
    cfg = load_config()
    meta = _fake_meta(
        tmp_path,
        parse_cmd=_fake_text_toolchain(tmp_path),
        output_format="text",
        error_regex=TEXT_TOOLCHAIN_ERROR_REGEX,
    )
    result = run_verifier("this is BAD input\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["exit_code"] == 1
    assert result["errors"] == [
        {"file": "candidate.fixture", "line": 3, "col": None, "code": None,
         "message": "bad thing found", "severity": "error"}
    ]
    assert result["warnings"] == [
        {"file": "candidate.fixture", "line": 5, "col": None, "code": None,
         "message": "minor issue", "severity": "warning"}
    ]


def test_run_verifier_text_mode_ok_on_clean_input(tmp_path):
    cfg = load_config()
    meta = _fake_meta(
        tmp_path,
        parse_cmd=_fake_text_toolchain(tmp_path),
        output_format="text",
        error_regex=TEXT_TOOLCHAIN_ERROR_REGEX,
    )
    result = run_verifier("this is clean input\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["exit_code"] == 0


def test_run_verifier_text_mode_without_error_regex_is_harness_error(tmp_path):
    cfg = load_config()
    meta = _fake_meta(tmp_path, parse_cmd=_fake_text_toolchain(tmp_path), output_format="text")
    result = run_verifier("BAD\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "EHARNESS"


def test_run_verifier_text_mode_invalid_regex_is_harness_error(tmp_path):
    cfg = load_config()
    meta = _fake_meta(
        tmp_path, parse_cmd=_fake_text_toolchain(tmp_path),
        output_format="text", error_regex="(unclosed[",
    )
    result = run_verifier("BAD\n", "parse", meta=meta, cfg=cfg)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "EHARNESS"
