"""The interface between the harness and the corpus/verifier side.

00_ARCHITECTURE.md #2 is explicit: Ollama never talks to the MCP server, the
harness is the only component that talks to both. This module is the harness
side of that wire -- everywhere `loop.py` needs corpus data or a verifier
run, it calls through `ToolClient`, never anything concrete.

In Phase 2 the lead agent wires a real MCP client (stdio JSON-RPC to
`ashlar/mcp/server.py`) that implements this exact Protocol. That should be a
plug, not a rewrite: the five method signatures below are copied verbatim
from 00_ARCHITECTURE.md #6.

Tonight, `ashlar/mcp/` is being built concurrently in another worktree and is
not importable here, so this module also ships `FakeToolClient` -- a fully
in-memory, hand-scriptable implementation used by every harness test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolClient(Protocol):
    """Exact signatures from 00_ARCHITECTURE.md #6. A tool never raises to
    the model -- on failure it returns `{"error": "<message>"}`; that rule
    is enforced by whatever implements this, not by callers."""

    def lookup_symbol(self, name: str) -> dict[str, Any]:
        """Confirm a symbol exists and where it is legal."""
        ...

    def grep_corpus(self, pattern: str, limit: int = 20, kind: str = "all") -> list[dict[str, Any]]:
        """Regex search across documentation and example source."""
        ...

    def get_examples(self, symbol: str, n: int = 3) -> list[dict[str, Any]]:
        """Real, verified usages of a symbol from the example corpus."""
        ...

    def read_file(self, path: str, start: int = 1, end: int = -1) -> dict[str, Any]:
        """Read a line range from a corpus file, confined to the corpus root."""
        ...

    def verify(self, source: str, run: bool = False, stdin: str = "") -> dict[str, Any]:
        """Compile/parse (and optionally run) candidate source in a sandbox.
        Returns the 00_ARCHITECTURE.md #5 verifier result contract, verbatim."""
        ...


def _not_found(name: str) -> dict[str, Any]:
    return {"found": False, "name": name}


def _ok_verify(stdout: str = "") -> dict[str, Any]:
    return {
        "ok": True,
        "errors": [],
        "warnings": [],
        "stdout": stdout,
        "stderr": "",
        "exit_code": 0,
        "duration_ms": 1,
    }


@dataclass
class FakeToolClient:
    """In-memory `ToolClient` for tests. Fully scriptable:

    - `symbols`: name -> lookup_symbol() result dict
    - `examples`: symbol -> list of get_examples() result dicts
    - `grep_hits`: pattern substring -> list of grep_corpus() result dicts
      (matched by substring containment against the requested pattern; the
      first matching key wins, so put more specific keys first if it matters)
    - `verify_fn`: callable(source, run, stdin) -> verifier result dict.
      Defaults to the same contract as `corpora/stub/verifier.py`: ok unless
      the literal string "FAIL" appears in source, in which case a
      synthetic E041 at line 3.
    - `read_files`: path -> full text, sliced by (start, end) on read_file.

    All calls are recorded in `self.calls` as (tool_name, kwargs) tuples so
    tests can assert on what the loop actually invoked.
    """

    symbols: dict[str, dict[str, Any]] = field(default_factory=dict)
    examples: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    grep_hits: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    read_files: dict[str, str] = field(default_factory=dict)
    verify_fn: Any = None
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list, repr=False)

    def lookup_symbol(self, name: str) -> dict[str, Any]:
        self.calls.append(("lookup_symbol", {"name": name}))
        return self.symbols.get(name, _not_found(name))

    def grep_corpus(self, pattern: str, limit: int = 20, kind: str = "all") -> list[dict[str, Any]]:
        self.calls.append(("grep_corpus", {"pattern": pattern, "limit": limit, "kind": kind}))
        try:
            re.compile(pattern)
        except re.error as e:
            return [{"error": f"invalid pattern: {e}"}]
        for key, hits in self.grep_hits.items():
            if key and key in pattern:
                return hits[:limit]
        return []

    def get_examples(self, symbol: str, n: int = 3) -> list[dict[str, Any]]:
        self.calls.append(("get_examples", {"symbol": symbol, "n": n}))
        return self.examples.get(symbol, [])[:n]

    def read_file(self, path: str, start: int = 1, end: int = -1) -> dict[str, Any]:
        self.calls.append(("read_file", {"path": path, "start": start, "end": end}))
        if ".." in path or path.startswith("/"):
            return {"error": f"path traversal rejected: {path}"}
        text = self.read_files.get(path)
        if text is None:
            return {"error": f"not found: {path}"}
        lines = text.splitlines()
        s = max(1, start)
        e = len(lines) if end == -1 else min(end, len(lines))
        return {"file": path, "start": s, "end": e, "text": "\n".join(lines[s - 1:e]), "truncated": False}

    def verify(self, source: str, run: bool = False, stdin: str = "") -> dict[str, Any]:
        self.calls.append(("verify", {"source": source, "run": run, "stdin": stdin}))
        if self.verify_fn:
            return self.verify_fn(source, run, stdin)
        if "FAIL" in source:
            return {
                "ok": False,
                "errors": [{
                    "file": "candidate", "line": 3, "col": 1, "code": "E041",
                    "message": "stub verifier: source contains literal 'FAIL'",
                    "severity": "error",
                }],
                "warnings": [], "stdout": "", "stderr": "", "exit_code": 1, "duration_ms": 1,
            }
        return _ok_verify(stdout="stub run ok\n" if run else "")
