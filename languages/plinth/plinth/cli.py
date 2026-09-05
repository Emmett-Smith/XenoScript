#!/usr/bin/env python3
"""PLINTH CLI. This is the contract the sandbox calls
(00_ARCHITECTURE.md Sec 4/5, 01_LANGUAGE.md Sec 7).

    plinth parse [--json] FILE     # exit 0 clean, 1 if errors
    plinth run   [--json] FILE     # parse then execute; trace to stdout
    plinth symbols --json          # dump built-in grammar as ground truth

Must run with zero pip install / venv, using only the system python3,
invoked as `python3 languages/plinth/plinth/cli.py <cmd> ...` with cwd =
repo root. Bootstraps sys.path so plain `import lexer` / `from plinth
import lexer` both work regardless of how this file is invoked.

--json is accepted for parse/run but is effectively a no-op: this CLI
*always* emits JSON on stdout for parse/run/symbols. There is no
human-readable mode -- 00_ARCHITECTURE.md Sec 4 says the sandbox parses
"the entire stdout as one JSON document" for whatever command meta.yaml
specifies, so anything else on stdout would be a contract violation.
"""
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # languages/plinth/plinth
_PARENT = _HERE.parent                            # languages/plinth
for _p in (str(_HERE), str(_PARENT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lexer import PlinthError, tokenize  # noqa: E402
import parser as P  # noqa: E402
import checker as C  # noqa: E402
import runtime as R  # noqa: E402
import symbols as S  # noqa: E402


def _result(ok, errors=None, warnings=None, stdout="", stderr="", exit_code=None, duration_ms=0):
    if exit_code is None:
        exit_code = 0 if ok else 1
    return {
        "ok": ok,
        "errors": errors or [],
        "warnings": warnings or [],
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
    }


def _error_entry(filename, err):
    return {
        "file": filename,
        "line": err.line,
        "col": err.col if err.col and err.col > 0 else None,
        "code": err.code,
        "message": err.message,
        "severity": "error",
    }


def _run_static(filename, source):
    """Lex + parse + check. Returns (world_or_None, error_or_None)."""
    try:
        program = P.parse_source(source, filename)
        world = C.check_program(program)
        return world, None
    except PlinthError as e:
        return None, e


def cmd_parse(filename):
    t0 = time.perf_counter()
    try:
        source = Path(filename).read_text()
    except OSError as e:
        dur = int((time.perf_counter() - t0) * 1000)
        print(json.dumps(_result(
            False,
            errors=[{"file": filename, "line": 1, "col": None, "code": "EHARNESS",
                     "message": f"cannot read file: {e}", "severity": "error"}],
            stderr=str(e), duration_ms=dur,
        )))
        return 1

    world, err = _run_static(filename, source)
    dur = int((time.perf_counter() - t0) * 1000)
    if err is not None:
        print(json.dumps(_result(False, errors=[_error_entry(filename, err)], duration_ms=dur)))
        return 1
    print(json.dumps(_result(True, duration_ms=dur)))
    return 0


def cmd_run(filename):
    t0 = time.perf_counter()
    try:
        source = Path(filename).read_text()
    except OSError as e:
        dur = int((time.perf_counter() - t0) * 1000)
        print(json.dumps(_result(
            False,
            errors=[{"file": filename, "line": 1, "col": None, "code": "EHARNESS",
                     "message": f"cannot read file: {e}", "severity": "error"}],
            stderr=str(e), duration_ms=dur,
        )))
        return 1

    world, err = _run_static(filename, source)
    if err is not None:
        dur = int((time.perf_counter() - t0) * 1000)
        print(json.dumps(_result(False, errors=[_error_entry(filename, err)], duration_ms=dur)))
        return 1

    if world.scenario is None:
        dur = int((time.perf_counter() - t0) * 1000)
        print(json.dumps(_result(
            False,
            errors=[{"file": filename, "line": 1, "col": None, "code": "EHARNESS",
                     "message": "no scenario defined; nothing to run", "severity": "error"}],
            duration_ms=dur,
        )))
        return 1

    try:
        trace_lines = R.simulate(world)
    except PlinthError as e:
        dur = int((time.perf_counter() - t0) * 1000)
        partial = getattr(e, "partial_trace", [])
        stdout = ("\n".join(partial) + "\n") if partial else ""
        print(json.dumps(_result(
            False, errors=[_error_entry(filename, e)], stdout=stdout, duration_ms=dur,
        )))
        return 1

    dur = int((time.perf_counter() - t0) * 1000)
    stdout = "\n".join(trace_lines) + "\n"
    print(json.dumps(_result(True, stdout=stdout, duration_ms=dur)))
    return 0


def cmd_symbols():
    print(json.dumps(S.build_symbols_payload()))
    return 0


def main(argv):
    args = [a for a in argv if a != "--json"]
    if not args:
        print(json.dumps(_result(
            False,
            errors=[{"file": "", "line": 1, "col": None, "code": "EHARNESS",
                     "message": "no subcommand given; expected parse, run, or symbols",
                     "severity": "error"}],
        )))
        return 1

    cmd = args[0]
    rest = args[1:]

    if cmd == "symbols":
        return cmd_symbols()
    if cmd == "parse":
        if not rest:
            print(json.dumps(_result(
                False,
                errors=[{"file": "", "line": 1, "col": None, "code": "EHARNESS",
                         "message": "parse requires a FILE argument", "severity": "error"}],
            )))
            return 1
        return cmd_parse(rest[0])
    if cmd == "run":
        if not rest:
            print(json.dumps(_result(
                False,
                errors=[{"file": "", "line": 1, "col": None, "code": "EHARNESS",
                         "message": "run requires a FILE argument", "severity": "error"}],
            )))
            return 1
        return cmd_run(rest[0])

    print(json.dumps(_result(
        False,
        errors=[{"file": "", "line": 1, "col": None, "code": "EHARNESS",
                 "message": f"unknown subcommand '{cmd}'; expected parse, run, or symbols",
                 "severity": "error"}],
    )))
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover - defensive last resort
        # Never let an internal bug break the "stdout is always one JSON
        # document" contract (00_ARCHITECTURE.md Sec 4/5). A crash here is
        # a bug in this interpreter, not the candidate source, but the
        # sandbox layer must still get parseable JSON.
        print(json.dumps(_result(
            False,
            errors=[{"file": "", "line": 1, "col": None, "code": "EHARNESS",
                     "message": f"internal interpreter error: {exc}", "severity": "error"}],
            stderr=repr(exc),
        )))
        sys.exit(1)
