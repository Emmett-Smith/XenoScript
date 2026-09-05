#!/usr/bin/env python3
"""Stub toolchain for corpora/stub. Unblocks the harness/MCP/frontend before
PLINTH exists. Contract: ok unless source contains the literal string FAIL,
in which case emit a fabricated E041 at line 3. Output matches the verifier
result contract in specs/00_ARCHITECTURE.md #5 exactly.
"""
import json
import sys


def result(ok, errors=None, stdout=""):
    return {
        "ok": ok,
        "errors": errors or [],
        "warnings": [],
        "stdout": stdout,
        "stderr": "",
        "exit_code": 0 if ok else 1,
        "duration_ms": 1,
    }


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    cmd = args[0]

    if cmd == "symbols":
        print(json.dumps({"language": "stub", "symbols": []}))
        return

    path = args[1]
    source = open(path).read()
    if "FAIL" in source:
        r = result(False, errors=[{
            "file": path, "line": 3, "col": 1, "code": "E041",
            "message": "stub verifier: source contains literal 'FAIL'",
            "severity": "error",
        }])
    else:
        r = result(True, stdout="stub run ok\n" if cmd == "run" else "")
    print(json.dumps(r))


if __name__ == "__main__":
    main()
