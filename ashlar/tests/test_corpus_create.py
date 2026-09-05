"""POST /corpus/create -- onboarding a brand new corpus through the API,
per the feature brief this endpoint was built against (see the module
docstring above the route in ashlar/api/server.py).

Uses a tiny fake toolchain the same way ashlar/tests/test_sandbox.py's
``_fake_meta``/synthetic-script tests do -- a `python3 -c "..."` stand-in
for a real compiler, not a real one. That's deliberate: the point of this
endpoint is that it *requires* the caller to name a real, already-working
toolchain command, not that this test suite needs one installed.

Every test that creates a corpus under the real ``corpora/`` tree cleans it
up afterward via the ``_new_corpus_name`` fixture's teardown, so repeated
runs never collide and the repo is left exactly as it was found.
"""

from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient

from ashlar.api.server import app
from ashlar.config import REPO_ROOT

CORPORA_DIR = REPO_ROOT / "corpora"

# A fake "toolchain" that always parses clean -- stands in for a real
# compiler exactly like test_sandbox.py's synthetic scripts do.
_OK_PARSE_CMD = '["python3", "-c", "import json; print(json.dumps({\\"ok\\": True, \\"errors\\": []}))"]'


def _client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def _new_corpus_name():
    name = "zz_test_fixture_lang"
    target = CORPORA_DIR / name
    assert not target.exists(), f"leftover test corpus at {target}, clean up manually"
    yield name
    shutil.rmtree(target, ignore_errors=True)


def _base_fields(**overrides) -> dict:
    fields = {
        "name": "placeholder",
        "display_name": "Placeholder Lang",
        "extension": ".fx",
        "comment_prefix": "#",
        "parse_cmd": _OK_PARSE_CMD,
        "run_cmd": _OK_PARSE_CMD,
    }
    fields.update(overrides)
    return fields


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_create_corpus_end_to_end_with_fake_toolchain(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name, display_name="ZZ Test Fixture Lang")
    files = [
        ("docs", ("manual.md", b"# Manual\nsome docs\n", "text/markdown")),
        ("examples", ("sample.fx", b"define thing foo\n", "text/plain")),
    ]

    resp = client.post("/corpus/create", data=fields, files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["name"] == _new_corpus_name
    assert body["display_name"] == "ZZ Test Fixture Lang"
    assert body["examples"] == 1
    assert body["pairs"] == 0
    assert body["warnings"] == []

    corpus_dir = CORPORA_DIR / _new_corpus_name
    assert (corpus_dir / "meta.yaml").exists()
    assert (corpus_dir / "docs" / "manual.md").read_text() == "# Manual\nsome docs\n"
    assert (corpus_dir / "examples" / "sample.fx").read_text() == "define thing foo\n"
    # run_ingest actually ran for real -- its manifest artifact exists.
    assert (corpus_dir / ".index" / "manifest.json").exists()

    import yaml

    meta = yaml.safe_load((corpus_dir / "meta.yaml").read_text())
    assert meta["language"] == _new_corpus_name
    assert meta["verifier"]["parse"] == [
        "python3",
        "-c",
        'import json; print(json.dumps({"ok": True, "errors": []}))',
    ]


def test_created_corpus_shows_up_in_subsequent_get_corpora(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name)
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 200, resp.text

    resp2 = client.get("/corpora")
    names = [c["name"] for c in resp2.json()]
    assert _new_corpus_name in names


def test_no_docs_or_examples_warns_but_still_succeeds(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name)
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["warnings"], "expected a warning when no docs/examples were uploaded"


# ---------------------------------------------------------------------------
# Validation failures -- must leave zero trace under corpora/
# ---------------------------------------------------------------------------


def test_path_traversal_name_rejected():
    client = _client()
    fields = _base_fields(name="../../etc/evil")
    resp = client.post("/corpus/create", data=fields)
    assert 400 <= resp.status_code < 500
    assert "error" in resp.json()
    assert not (CORPORA_DIR / "evil").exists()
    assert not (CORPORA_DIR.parent.parent / "etc" / "evil").exists()


def test_path_traversal_name_with_slash_rejected():
    client = _client()
    fields = _base_fields(name="sub/dir")
    resp = client.post("/corpus/create", data=fields)
    assert 400 <= resp.status_code < 500
    assert "error" in resp.json()


def test_malformed_parse_cmd_json_rejected(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name, parse_cmd="not valid json")
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 400
    assert "parse_cmd" in resp.json()["error"]
    assert not (CORPORA_DIR / _new_corpus_name).exists()


def test_parse_cmd_must_be_nonempty_list_of_strings(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name, parse_cmd="[]")
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 400
    assert "parse_cmd" in resp.json()["error"]

    fields2 = _base_fields(name=_new_corpus_name, parse_cmd='["ok", 5]')
    resp2 = client.post("/corpus/create", data=fields2)
    assert resp2.status_code == 400
    assert not (CORPORA_DIR / _new_corpus_name).exists()


def test_invalid_error_regex_rejected_when_output_format_text(_new_corpus_name):
    client = _client()
    fields = _base_fields(
        name=_new_corpus_name,
        output_format="text",
        error_regex="(unclosed[",
    )
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 400
    assert "error_regex" in resp.json()["error"]
    assert not (CORPORA_DIR / _new_corpus_name).exists()


def test_error_regex_required_when_output_format_text(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name, output_format="text")
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 400
    assert "error_regex" in resp.json()["error"]
    assert not (CORPORA_DIR / _new_corpus_name).exists()


def test_duplicate_name_rejected(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name)
    first = client.post("/corpus/create", data=fields)
    assert first.status_code == 200, first.text

    second = client.post("/corpus/create", data=_base_fields(name=_new_corpus_name))
    assert 400 <= second.status_code < 500
    assert "error" in second.json()
    assert "already exists" in second.json()["error"]


def test_invalid_extension_rejected(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name, extension="fx")  # missing leading dot
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 400
    assert not (CORPORA_DIR / _new_corpus_name).exists()


def test_invalid_chunk_strategy_rejected(_new_corpus_name):
    client = _client()
    fields = _base_fields(name=_new_corpus_name, chunk_strategy="nonsense")
    resp = client.post("/corpus/create", data=fields)
    assert resp.status_code == 400
    assert not (CORPORA_DIR / _new_corpus_name).exists()
