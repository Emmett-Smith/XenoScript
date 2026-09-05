"""01_LANGUAGE.md Sec 9 "The pairs": 15 (task, expected) pairs, each with
a solution.plth used only for grading. solution.plth must never leak into
retrieval (the backend's ingest is responsible for the actual skip rule,
per 01_LANGUAGE.md Sec 9 -- this test only confirms the filename
convention the skip rule depends on, and that every pair is internally
consistent: task.txt exists, solution.plth runs clean, and its trace
matches expected.txt byte for byte)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PAIRS_DIR = ROOT / "corpora" / "plinth" / "pairs"
CLI = ROOT / "languages" / "plinth" / "plinth" / "cli.py"

PAIR_DIRS = sorted(p for p in PAIRS_DIR.iterdir() if p.is_dir())


def test_exactly_15_pairs():
    assert len(PAIR_DIRS) == 15


@pytest.mark.parametrize("pair_dir", PAIR_DIRS, ids=lambda p: p.name)
def test_pair_has_required_files(pair_dir):
    assert (pair_dir / "task.txt").exists()
    assert (pair_dir / "expected.txt").exists()
    assert (pair_dir / "solution.plth").exists()


@pytest.mark.parametrize("pair_dir", PAIR_DIRS, ids=lambda p: p.name)
def test_solution_runs_clean_and_matches_expected(pair_dir):
    proc = subprocess.run(
        [sys.executable, str(CLI), "run", "--json", str(pair_dir / "solution.plth")],
        capture_output=True, text=True,
    )
    result = json.loads(proc.stdout)
    assert result["ok"] is True, result["errors"]
    expected = (pair_dir / "expected.txt").read_text()
    assert result["stdout"] == expected


@pytest.mark.parametrize("pair_dir", PAIR_DIRS, ids=lambda p: p.name)
def test_expected_trace_has_no_trailing_whitespace_and_ends_with_newline(pair_dir):
    text = (pair_dir / "expected.txt").read_text()
    assert text.endswith("\n") and not text.endswith("\n\n")
    for line in text.splitlines():
        assert line == line.rstrip(), f"trailing whitespace in {pair_dir.name}: {line!r}"


def test_solution_filename_convention_matches_ingest_skip_rule():
    """The backend's ingest is responsible for skipping pairs/*/solution.plth
    (01_LANGUAGE.md Sec 9). This test just locks down the filename every
    pair actually uses, so that skip rule has something to match."""
    for pair_dir in PAIR_DIRS:
        files = {p.name for p in pair_dir.iterdir()}
        assert "solution.plth" in files
        # no alternate solution filenames that would slip past a
        # "pairs/*/solution.plth" glob skip-rule
        plth_files = [n for n in files if n.endswith(".plth")]
        assert plth_files == ["solution.plth"]
