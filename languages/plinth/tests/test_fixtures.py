"""Every error code E001-E072 must be reachable via a dedicated fixture
(01_LANGUAGE.md Sec 10 definition-of-done). Invokes the real CLI, exactly
as the sandbox will, so this also exercises the --json contract end to
end for the error path."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CLI = ROOT / "languages" / "plinth" / "plinth" / "cli.py"

RUNTIME_CODES = {"E070", "E071", "E072"}

ALL_CODES = [
    "E001", "E002", "E003", "E004",
    "E010", "E011", "E012",
    "E020", "E021", "E022",
    "E030", "E031",
    "E040", "E041", "E042", "E043",
    "E050", "E051", "E052",
    "E060",
    "E070", "E071", "E072",
]


def _invoke(code):
    fpath = FIXTURES_DIR / f"{code}.plth"
    cmd = "run" if code in RUNTIME_CODES else "parse"
    proc = subprocess.run(
        [sys.executable, str(CLI), cmd, "--json", str(fpath)],
        capture_output=True, text=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("code", ALL_CODES)
def test_fixture_exists(code):
    assert (FIXTURES_DIR / f"{code}.plth").exists(), f"missing fixture for {code}"


@pytest.mark.parametrize("code", ALL_CODES)
def test_fixture_produces_expected_code(code):
    result = _invoke(code)
    assert result["ok"] is False
    codes = [e["code"] for e in result["errors"]]
    assert code in codes, f"{code} fixture produced {codes} instead"


@pytest.mark.parametrize("code", ALL_CODES)
def test_fixture_error_has_line_and_message(code):
    result = _invoke(code)
    err = result["errors"][0]
    assert err["line"] >= 1
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert err["severity"] == "error"
