"""Offline verifier sandbox. No network egress, ever.

Runs a corpus's verifier toolchain (``parse`` / ``run``) against candidate
source and normalizes whatever it prints to the verifier result contract in
``specs/00_ARCHITECTURE.md`` #5. Corpus-agnostic by construction: every
language-specific detail (the command, the file extension, the timeout)
comes from ``meta.yaml`` via ``ashlar.config`` -- this module never branches
on a language name.

Only ``sandbox.mode: subprocess`` is implemented tonight, per explicit
pre-decision (specs/02_BACKEND.md #4, #6). ``container`` mode is deliberately
left unimplemented -- see ``run_verifier`` below -- rather than silently
falling back, so the interface stays honest about what actually runs.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ashlar.config import (
    REPO_ROOT,
    Config,
    CorpusMeta,
    effective_sandbox_mode,
    load_config,
    load_corpus_meta,
)

VALID_MODES = ("parse", "run")


def _harness_error(
    message: str,
    exit_code: int = -1,
    duration_ms: float = 0.0,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, Any]:
    """The synthetic-error shape required whenever the toolchain itself
    misbehaves (bad JSON, timeout, launch failure). Never silently pass."""
    return {
        "ok": False,
        "errors": [
            {
                "file": None,
                "line": None,
                "col": None,
                "code": "EHARNESS",
                "message": message,
                "severity": "error",
            }
        ],
        "warnings": [],
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
    }


def _substitute(template: list[str], file_path: Path) -> list[str]:
    return [part.replace("{file}", str(file_path)) for part in template]


def run_verifier(
    source: str,
    mode: str,
    stdin: str = "",
    *,
    meta: CorpusMeta | None = None,
    cfg: Config | None = None,
) -> dict[str, Any]:
    """Run the active corpus's verifier against ``source``.

    ``mode`` is ``'parse'`` or ``'run'``. Returns the
    ``specs/00_ARCHITECTURE.md`` #5 result shape unconditionally -- callers
    never need to catch an exception from a well-formed call (the one
    deliberate exception is ``NotImplementedError`` for unimplemented
    ``container`` sandbox mode, which is a build-time configuration error,
    not a runtime verifier failure).

    ``meta``/``cfg`` are optional overrides for tests. Production callers
    (the MCP server) omit them; this then loads whichever corpus
    ``config.yaml`` names, so this module never hardcodes a language.
    """
    if mode not in VALID_MODES:
        return _harness_error(f"unknown verifier mode {mode!r}, expected one of {VALID_MODES}")

    cfg = cfg or load_config()
    meta = meta or load_corpus_meta(cfg.corpus)

    sandbox_mode = effective_sandbox_mode(cfg, meta)
    if sandbox_mode == "container":
        raise NotImplementedError(
            "container sandbox mode not implemented -- see specs/02_BACKEND.md #4; "
            "subprocess mode is used for this session"
        )
    if sandbox_mode != "subprocess":
        return _harness_error(f"unknown sandbox mode {sandbox_mode!r}")

    template = meta.verifier.parse if mode == "parse" else meta.verifier.run
    if not template:
        return _harness_error(f"corpus {meta.language!r} defines no verifier.{mode} command")

    with TemporaryDirectory() as tmpdir:
        candidate_path = Path(tmpdir) / f"candidate{meta.extension}"
        candidate_path.write_text(source)

        cmd = _substitute(template, candidate_path)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=meta.sandbox.timeout_s,
                input=stdin,
            )
        except subprocess.TimeoutExpired:
            # subprocess.run kills the process for us before re-raising.
            duration_ms = (time.monotonic() - start) * 1000
            return _harness_error(
                f"verifier timed out after {meta.sandbox.timeout_s}s (wall-clock cap)",
                duration_ms=duration_ms,
            )
        except OSError as exc:
            duration_ms = (time.monotonic() - start) * 1000
            return _harness_error(f"failed to launch verifier: {exc}", duration_ms=duration_ms)

        duration_ms = (time.monotonic() - start) * 1000

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            # Toolchain misbehavior: our contract says every verifier prints
            # one JSON document to stdout. Never silently pass.
            return _harness_error(
                "verifier did not print a single JSON document to stdout",
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )

        if not isinstance(payload, dict):
            return _harness_error(
                "verifier JSON output was not an object",
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )

        errors = payload.get("errors") or []
        # ok is derived, not trusted from the payload: "true only when errors
        # is empty and exit_code == 0" (00_ARCHITECTURE.md #5), so a
        # misbehaving toolchain that reports ok=true with a nonzero exit
        # can't slip a bad result past the loop.
        ok = len(errors) == 0 and proc.returncode == 0

        return {
            "ok": ok,
            "errors": errors,
            "warnings": payload.get("warnings") or [],
            "stdout": payload.get("stdout", proc.stdout),
            "stderr": payload.get("stderr", proc.stderr),
            "exit_code": proc.returncode,
            "duration_ms": payload.get("duration_ms", duration_ms),
        }
