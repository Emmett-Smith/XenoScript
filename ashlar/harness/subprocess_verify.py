"""A minimal, test-only `verify()` implementation that shells out to a real
corpus verifier via subprocess, per the `sandbox.mode: subprocess` fallback
described in 02_BACKEND.md #4.

This exists so the harness's "runs end to end against corpora/stub" test
(03_HARNESS.md #7) exercises the *actual* `corpora/stub/verifier.py` script
rather than a second hand-rolled reimplementation of its contract living in
`FakeToolClient`.

This is NOT the real sandbox. `ashlar/mcp/sandbox.py` (backend's territory,
built concurrently in another worktree tonight) owns container exec,
resource caps, and the real `--network=none` story. This module only knows
how to run `meta.yaml`'s verifier commands as a subprocess with a timeout and
normalize the result -- exactly the fallback path 02_BACKEND.md already
specifies, scoped down to what the harness needs for its own tests.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ashlar.config import CorpusMeta


def run_verifier(meta: CorpusMeta, source: str, mode: str = "parse", stdin: str = "", timeout_s: int | None = None) -> dict[str, Any]:
    """mode: 'parse' | 'run'. Returns the 00_ARCHITECTURE.md #5 contract."""
    cmd_template = meta.verifier.run if mode == "run" else meta.verifier.parse
    timeout = timeout_s or meta.sandbox.timeout_s

    with tempfile.TemporaryDirectory() as td:
        candidate = Path(td) / f"candidate{meta.extension}"
        candidate.write_text(source)
        cmd = [candidate.as_posix() if part == "{file}" else part for part in cmd_template]
        try:
            proc = subprocess.run(
                cmd, input=stdin, capture_output=True, text=True, timeout=timeout,
                cwd=meta.root.parent.parent,  # repo root, so relative script paths in meta.yaml resolve
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _harness_error(f"verifier timed out after {timeout}s")

        try:
            payload = json.loads(proc.stdout)
        except (json.JSONDecodeError, ValueError):
            return _harness_error(f"unparseable verifier output: {proc.stdout!r} stderr={proc.stderr!r}")

        payload.setdefault("warnings", [])
        payload.setdefault("stderr", proc.stderr)
        payload.setdefault("exit_code", proc.returncode)
        payload.setdefault("duration_ms", 0)
        # Never silently pass: enforce ok only when errors empty and exit 0.
        payload["ok"] = bool(payload.get("ok")) and not payload.get("errors") and payload["exit_code"] == 0
        return payload


def _harness_error(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "errors": [{"file": None, "line": None, "col": None, "code": "EHARNESS", "message": message, "severity": "error"}],
        "warnings": [],
        "stdout": "",
        "stderr": "",
        "exit_code": 1,
        "duration_ms": 0,
    }
