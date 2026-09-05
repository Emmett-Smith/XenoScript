"""01_LANGUAGE.md Sec 10 definition-of-done: all 15 examples parse clean
and `run` matches a committed golden trace."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = ROOT / "corpora" / "plinth" / "examples"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
CLI = ROOT / "languages" / "plinth" / "plinth" / "cli.py"

EXAMPLES = sorted(p.stem for p in EXAMPLES_DIR.glob("*.plth"))


def _invoke(cmd, fname):
    proc = subprocess.run(
        [sys.executable, str(CLI), cmd, "--json", str(EXAMPLES_DIR / f"{fname}.plth")],
        capture_output=True, text=True,
    )
    return json.loads(proc.stdout)


def test_exactly_15_examples():
    assert len(EXAMPLES) == 15


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_parses_clean(name):
    result = _invoke("parse", name)
    assert result["ok"] is True, result["errors"]
    assert result["exit_code"] == 0


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_runs_clean_and_matches_golden(name):
    result = _invoke("run", name)
    assert result["ok"] is True, result["errors"]
    golden = (GOLDEN_DIR / f"{name}.trace").read_text()
    assert result["stdout"] == golden


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_has_header_comment(name):
    text = (EXAMPLES_DIR / f"{name}.plth").read_text()
    assert text.startswith("#"), f"{name}.plth is missing its header comment"
