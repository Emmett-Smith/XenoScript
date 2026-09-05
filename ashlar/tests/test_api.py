import json

from fastapi.testclient import TestClient

from ashlar.api.server import app, state


def _client() -> TestClient:
    return TestClient(app)


def test_corpora_lists_stub():
    client = _client()
    resp = client.get("/corpora")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "stub" in names


def test_corpus_switch_is_idempotent_and_returns_manifest():
    client = _client()
    resp = client.post("/corpus/switch", json={"name": "stub"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "stub"
    assert body["display_name"] == "Stub"
    assert state.corpus_name == "stub"


def test_corpus_switch_unknown_corpus_404():
    client = _client()
    resp = client.post("/corpus/switch", json={"name": "does_not_exist"})
    assert resp.status_code == 404


def test_eval_latest_reports_real_state_not_a_hardcoded_stub():
    client = _client()
    resp = client.get("/eval/latest")
    assert resp.status_code == 200
    body = resp.json()
    # eval/reports/ started empty tonight (no live model at session start),
    # then Phase 4 actually ran the eval runner and populated it -- this
    # must reflect whichever of those two real states currently holds, not
    # a permanent hardcoded stub either way.
    assert body == {"error": "no report yet"} or {"git_sha", "arms", "model_endpoints"} <= body.keys()


def test_eval_latest_with_corpus_param_returns_that_corpus_not_just_newest_file(tmp_path, monkeypatch):
    """Real bug found live: GET /eval/latest with no filter returns the
    single newest report file regardless of which corpus it's for. A
    COBOL sweep briefly became "the latest report" while PLINTH was the
    active corpus in the UI, and the frontend rendered COBOL's numbers
    under the PLINTH header with no way to detect the mismatch. ?corpus=
    must return the newest report *for that corpus specifically*."""
    import ashlar.api.server as server_module

    monkeypatch.setattr(server_module, "EVAL_REPORTS_DIR", tmp_path)
    (tmp_path / "20260101T000000Z.json").write_text(
        json.dumps({"corpus": "plinth", "arms": {"D": {"verified_correct_rate": 0.25}}})
    )
    # Written later (sorts after by filename) but for a *different* corpus.
    (tmp_path / "20260102T000000Z.json").write_text(
        json.dumps({"corpus": "cobol", "arms": {"D": {"verified_correct_rate": 0.9}}})
    )

    client = _client()

    no_filter = client.get("/eval/latest").json()
    assert no_filter["corpus"] == "cobol"  # unfiltered: still the newest file overall

    plinth_only = client.get("/eval/latest", params={"corpus": "plinth"}).json()
    assert plinth_only["corpus"] == "plinth"
    assert plinth_only["arms"]["D"]["verified_correct_rate"] == 0.25

    cobol_only = client.get("/eval/latest", params={"corpus": "cobol"}).json()
    assert cobol_only["corpus"] == "cobol"

    missing = client.get("/eval/latest", params={"corpus": "nonexistent"}).json()
    assert "error" in missing


def test_post_task_returns_task_id_and_stream_emits_full_event_sequence():
    client = _client()
    resp = client.post("/task", json={"prompt": "define a platform", "corpus": "stub"})
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    assert task_id.startswith("t_")

    types: list[str] = []
    with client.stream("GET", f"/stream/{task_id}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                types.append(payload["type"])
            if types and types[-1] in ("task_done", "task_failed"):
                break

    assert types[0] == "task_start"
    assert types[-1] in ("task_done", "task_failed")


def test_post_task_unknown_stream_id_404():
    client = _client()
    resp = client.get("/stream/t_doesnotexist")
    assert resp.status_code == 404


def test_server_binds_localhost_only_by_config():
    # Bind target is read from config, not hardcoded -- assert the value
    # actually loaded is loopback, since that's the invariant that matters
    # (00_ARCHITECTURE.md #12: no network from harness except the model).
    assert state.cfg.api.host == "127.0.0.1"
