"""Offline verification. 03_HARNESS.md #6: assert zero outbound network
connections during a task run.

Lives under `eval/` per the repo layout in 00_ARCHITECTURE.md #3, even
though it's built by the harness agent -- 03_HARNESS.md #6 explicitly
carves out this one exception to the `ashlar/harness/`, `ashlar/api/`,
`prompts/` directory boundary.

Approach chosen (documented per the task brief's "your call"): monkeypatch
`socket.socket.connect` / `connect_ex` for the duration of a `FakeModel`
+ `FakeToolClient` (subprocess-verifier-backed) task run, and assert they
are never called with a non-loopback address. This is a process-level hook,
not an OS packet capture -- good enough to catch "the OpenAI client tried to
phone home," "a library did a version-check ping," or "something tried to
fetch a font/embedding model," all of which go through `socket.connect`
before anything hits the wire. It does NOT catch e.g. a raw AF_UNIX socket
or a subprocess that opens its own socket outside this interpreter (not a
concern for a `FakeModel`-driven run, since nothing here shells out except
the stub verifier itself, which opens no sockets).

Run directly:

    python -m eval.offline_check

Exits non-zero and prints the offending address if any non-loopback
connection attempt is observed.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class NetworkCallDetected(AssertionError):
    pass


def _guarded_connect(real_connect):
    def wrapper(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOOPBACK_HOSTS:
            raise NetworkCallDetected(f"outbound connection attempted to {address!r}")
        return real_connect(self, address, *a, **k)

    return wrapper


def run_offline_task_and_assert_no_network() -> None:
    """Runs one full harness task against `corpora/stub` with `FakeModel`
    and a subprocess-backed `FakeToolClient` (the same fixtures the harness
    test suite uses), with socket.connect/connect_ex patched to reject any
    non-loopback address. Raises `NetworkCallDetected` on violation."""
    from ashlar.config import load_corpus_meta
    from ashlar.harness.loop import Corpus, HarnessDeps, run_task
    from ashlar.harness.memory import Memory
    from ashlar.harness.model import FakeModel
    from ashlar.harness.subprocess_verify import run_verifier
    from ashlar.harness.tool_client import FakeToolClient

    meta = load_corpus_meta("stub")

    def verify(source: str, run: bool = False, stdin: str = ""):
        return run_verifier(meta, source, mode="run" if run else "parse", stdin=stdin)

    fixtures = REPO_ROOT / "ashlar" / "harness" / "fixtures"
    model = FakeModel.from_fixtures(fixtures, ["attempt1_fail.stub", "attempt2_pass.stub"])
    tool_client = FakeToolClient(verify_fn=verify)

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        memory = Memory(Path(td) / "symbols.db")
        corpus = Corpus(meta=meta, symbol_names=["platform", "altitude"], pairs={})
        deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        socket.socket.connect = _guarded_connect(original_connect)  # type: ignore[method-assign]
        socket.socket.connect_ex = _guarded_connect(original_connect_ex)  # type: ignore[method-assign]
        try:
            events: list[dict] = []
            result = run_task("define a platform with altitude", corpus, events.append, deps)
        finally:
            socket.socket.connect = original_connect  # type: ignore[method-assign]
            socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]

    assert result.ok is True, f"offline task run did not complete as expected: {result}"


def main() -> int:
    try:
        run_offline_task_and_assert_no_network()
    except NetworkCallDetected as e:
        print(f"OFFLINE CHECK FAILED: {e}", file=sys.stderr)
        return 1
    print("OFFLINE CHECK PASSED: zero outbound connections during task run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
