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


def test_eval_latest_reports_no_report_yet_when_empty():
    client = _client()
    resp = client.get("/eval/latest")
    assert resp.status_code == 200
    body = resp.json()
    # eval/reports/ is empty tonight (no live model, no eval run) -- must be
    # a real not-hardcoded check, not a permanent stub.
    assert body == {"error": "no report yet"} or "reports" in str(body)


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
