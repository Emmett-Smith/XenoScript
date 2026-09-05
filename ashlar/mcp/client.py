"""In-process adapter: `ashlar.harness.tool_client.ToolClient` implemented by
calling `ashlar.mcp.server`'s tool functions directly.

Phase 2 integration note: `00_ARCHITECTURE.md` #2's contract is that Ollama
never talks to the MCP server and the harness is the only component that
talks to both sides -- it does not mandate that the harness-to-MCP leg run
over the stdio JSON-RPC transport specifically. The `mcp` package's
`@mcp.tool()` decorator leaves the underlying functions as plain, directly
callable Python functions (confirmed in the backend agent's Phase 1 report),
and both sides already run in the same process/venv for the API server, so
calling them in-process avoids a redundant subprocess-per-task without
changing the tool contract at all. A real stdio-subprocess `ToolClient`
could replace this one later without touching `ashlar/harness/loop.py` --
the whole point of the Protocol boundary.
"""

from __future__ import annotations

from typing import Any

from ashlar.mcp import server as _server


class RealToolClient:
    """Delegates every call straight to `ashlar.mcp.server`'s tool functions,
    which already enforce every 00_ARCHITECTURE.md #6 contract (path
    traversal rejection, invalid-regex handling, never raising to the
    caller)."""

    def lookup_symbol(self, name: str) -> dict[str, Any]:
        return _server.lookup_symbol(name)

    def grep_corpus(self, pattern: str, limit: int = 20, kind: str = "all") -> list[dict[str, Any]]:
        result = _server.grep_corpus(pattern, limit=limit, kind=kind)
        return result if isinstance(result, list) else [result]

    def get_examples(self, symbol: str, n: int = 3) -> list[dict[str, Any]]:
        result = _server.get_examples(symbol, n=n)
        return result if isinstance(result, list) else [result]

    def read_file(self, path: str, start: int = 1, end: int = -1) -> dict[str, Any]:
        return _server.read_file(path, start=start, end=end)

    def verify(self, source: str, run: bool = False, stdin: str = "") -> dict[str, Any]:
        return _server.verify(source, run=run, stdin=stdin)
