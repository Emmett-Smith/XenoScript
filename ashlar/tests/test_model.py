from pathlib import Path

from ashlar.harness.model import FakeModel

FIXTURES = Path(__file__).resolve().parent.parent / "harness" / "fixtures"


def test_fake_model_scripts_by_call_count():
    model = FakeModel(responses=["first", "second"])
    assert model.generate("sys", "ctx", "prompt", "") == "first"
    assert model.generate("sys", "ctx", "prompt", "") == "second"
    # more calls than responses -> repeats the last one
    assert model.generate("sys", "ctx", "prompt", "") == "second"


def test_fake_model_records_calls_for_assertions():
    model = FakeModel(responses=["x"])
    model.generate("SYS", "CTX", "PROMPT", "HIST")
    assert model.calls[0] == {"system": "SYS", "context": "CTX", "prompt": "PROMPT", "history": "HIST"}


def test_fake_model_streams_tokens_that_reassemble_source():
    model = FakeModel(responses=["define platform uav_01"])
    tokens = []
    out = model.generate("s", "c", "p", "", on_token=tokens.append)
    assert "".join(tokens) == out == "define platform uav_01"
    assert len(tokens) > 1  # actually streamed, not one giant chunk


def test_fake_model_from_fixtures_loads_files_in_order():
    model = FakeModel.from_fixtures(FIXTURES, ["attempt1_fail.stub", "attempt2_pass.stub"])
    first = model.generate("s", "c", "p", "")
    second = model.generate("s", "c", "p", "")
    assert "FAIL" in first
    assert "FAIL" not in second


def test_fake_model_never_touches_network(monkeypatch):
    import socket

    def _boom(*a, **k):
        raise AssertionError("FakeModel must not open sockets")

    monkeypatch.setattr(socket.socket, "connect", _boom)
    model = FakeModel(responses=["hi"])
    assert model.generate("s", "c", "p", "") == "hi"
