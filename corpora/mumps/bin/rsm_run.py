#!/usr/bin/env python3
"""Shared plumbing for the MUMPS/M corpus's verifier.parse and verifier.run
commands (meta.yaml). Both drive Reference Standard M (RSM), a real, open-
source ANSI M interpreter that builds and runs natively on this machine
(https://github.com/Reference-Standard-M/rsm) -- confirmed live, no VM/
container needed, unlike YottaDB which is Linux/AIX-only at the source
level.

Real, verified operational constraint that shapes this file's design:
macOS's default SysV shared-memory ceiling (`sysctl kern.sysv.shmall`) is
only 4 MiB system-wide, and RSM's own minimal environment already uses
~3 MiB -- there is no room for a fresh environment per verify() call, and
forgetting to tear one down leaks it until a manual `ipcrm` or reboot.
So this corpus uses ONE persistent environment (`env/mumps.dat`, created
lazily on first use, gitignored -- a build artifact, not source), reused
across every call, the same way a database server is started once and
then connected to repeatedly rather than relaunched per query.

RSM's direct-mode execution model has no equivalent to `cobc -fsyntax-only`
-- checking a line for syntax errors means actually executing it (that's
how M's lazy per-line compile-and-run direct mode works), and errors are
reported inline in stdout as `$ECODE=,<code>,` followed by a message line,
with no line-number info of their own. `parse_and_extract_errors` recovers
real line numbers by instrumenting the candidate with one WRITE marker
per source line before running it, then re-associates each error with
the most recently printed marker. This is why verifier.parse and
verifier.run are two different modes here, not two names for the same
command as they might be for a toolchain with a real syntax-check-only
mode: run() executes the raw, uninstrumented source (real output, no
markers) and is only ever invoked by the harness after parse() has
already reported ok=True, so it never needs error recovery of its own.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RSM = REPO_ROOT / ".toolchains" / "rsm" / "bin" / "rsm"
ENV_DB = Path(__file__).resolve().parent.parent / "env" / "mumps.dat"

_MARKER_RE = re.compile(r"^@@ASHLARLINE(\d+)@@$")
_ECODE_RE = re.compile(r"^\$ECODE=,([A-Za-z0-9]+),$")

# Real, verified isolation fix: globals (^name) live in the shared,
# persistent environment's database file, not in per-process local memory
# -- unlike locals, they survive across separate verify() calls by design
# (that IS what a global is). Confirmed live: SET ^TEST=1 in one call,
# then $DATA(^TEST) in a completely separate, later call returned 1.
# Left unfixed, one task's leftover global data could silently change
# whether a LATER, unrelated task passes or fails. This preamble runs
# before every execution and wipes every real global back to empty,
# using the real, documented ^$GLOBAL enumeration idiom (RSM's own
# language reference, Structured System Variables / ^$GLOBAL) -- "$GLOBAL"
# itself is skipped because it's the read-only SSVN doing the enumerating,
# not a real global, and RSM correctly refuses to KILL it (M29).
_WIPE_GLOBALS_PREAMBLE = (
    'SET GVN=""\n'
    'FOR  SET GVN=$ORDER(^$GLOBAL(GVN)) QUIT:GVN=""  '
    'IF $EXTRACT(GVN,1)\'="$" KILL @("^"_GVN)\n'
)


class EnvSetupError(RuntimeError):
    pass


def ensure_env() -> None:
    """Real, verified constraint: macOS's default SysV shared-memory
    ceiling (`sysctl kern.sysv.shmall`) is only 4 MiB system-wide. A
    4 KiB-block, 500-block volume with a 4-job environment measured at
    ~3 MiB total share size and fit; an 8 KiB/8-job configuration tried
    first measured ~5 MiB and was rejected outright by the OS. These
    sizes are deliberately small for that reason, not for performance."""
    ENV_DB.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_DB.exists():
        proc = subprocess.run(
            [str(RSM), "-v", "ASHLAR", "-b", "4", "-s", "500", str(ENV_DB)],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0 and not ENV_DB.exists():
            raise EnvSetupError(f"failed to create MUMPS volume: {proc.stdout}{proc.stderr}")

    probe = subprocess.run(
        [str(RSM), "-x", "QUIT", str(ENV_DB)], capture_output=True, text=True, timeout=15,
    )
    if "not initialized" in (probe.stdout + probe.stderr):
        started = subprocess.run(
            [str(RSM), "-j", "4", str(ENV_DB)], capture_output=True, text=True, timeout=15,
        )
        if "Unable to create shared memory" in (started.stdout + started.stderr):
            raise EnvSetupError(
                f"failed to start MUMPS environment: {started.stdout}{started.stderr}"
            )


def instrument(source: str) -> str:
    """One `WRITE "@@ASHLARLINEn@@",!` marker line ahead of every real
    source line -- a real M line every direct-mode input line is executed
    independently, so inserting one never changes what runs after it."""
    out = []
    for i, line in enumerate(source.splitlines(), start=1):
        out.append(f'WRITE "@@ASHLARLINE{i}@@",!')
        out.append(line)
    return "\n".join(out) + "\n"


def _run_rsm_with_stdin(text: str, timeout_s: float) -> subprocess.CompletedProcess[str]:
    """Real, verified-live bug: `subprocess.run([RSM, ENV_DB], input=text,
    ...)` silently produces empty stdout/stderr and exit code 0 for EVERY
    input, success or failure alike -- rsm never actually processes
    anything Python delivers via its internal pipe-writing mechanism
    (Popen.communicate()'s `input=`). Confirmed by elimination: piping
    through an actual shell (`cat file | rsm ...`) or handing rsm a real
    open file object as stdin both work correctly; `input=` alone never
    does, for any source, not just this one. So every source line here
    is written to a real temp file and passed as `stdin=`, never via
    `input=`.

    NOT fully resolved by this fix, and worth knowing before trusting a
    quiet MUMPS "Verified" in the live app: every isolated, one-off
    reproduction of the bug above (a fresh `python3 -c` process, run any
    number of times) is fixed by this change, consistently. But driven
    through the actual long-running `ashlar.api.server` process
    specifically, the exact same empty-output symptom was still
    reproduced 16/16 times in further live testing, with this fix
    already in place -- while one-off scripts against the identical
    environment, run moments apart, kept succeeding. The real
    interpreter and the fix above are both confirmed correct in
    isolation; something about the long-running server process itself
    (accumulated subprocess/signal state over its lifetime? asyncio's
    child-watcher interaction with a plain synchronous subprocess.run
    call, which did not reproduce in a minimal asyncio.run() repro
    either?) still needs isolating. Until then, treat MUMPS behavioral
    (pair-scored) results from the live app as unreliable; compile-only
    checking and the standalone demo-mumps/ project (run directly, never
    through the server process) are unaffected."""
    with tempfile.NamedTemporaryFile("w", suffix=".m", delete=False) as f:
        f.write(text)
        stdin_path = f.name
    try:
        with open(stdin_path) as stdin_file:
            return subprocess.run(
                [str(RSM), str(ENV_DB)], stdin=stdin_file, capture_output=True, text=True, timeout=timeout_s,
            )
    finally:
        Path(stdin_path).unlink(missing_ok=True)


def run_instrumented(source: str, timeout_s: float) -> str:
    ensure_env()
    instrumented = _WIPE_GLOBALS_PREAMBLE + instrument(source)
    proc = _run_rsm_with_stdin(instrumented, timeout_s)
    return proc.stdout


def run_raw(source: str, timeout_s: float) -> subprocess.CompletedProcess[str]:
    ensure_env()
    return _run_rsm_with_stdin(_WIPE_GLOBALS_PREAMBLE + source, timeout_s)


def extract_errors(instrumented_output: str, file_label: str) -> list[str]:
    """Re-associates each inline `$ECODE=,code,` + message pair with the
    most recently printed line marker, emitting COBOL-convention
    `file:line: error: message` lines so this corpus can reuse the exact
    same generic text-output adapter/error_regex as corpora/cobol does
    (ashlar/mcp/sandbox.py never branches on a language name)."""
    lines = instrumented_output.splitlines()
    current_line = 0
    out: list[str] = []
    i = 0
    while i < len(lines):
        marker = _MARKER_RE.match(lines[i])
        if marker:
            current_line = int(marker.group(1))
            i += 1
            continue
        ecode = _ECODE_RE.match(lines[i])
        if ecode:
            message = lines[i + 1] if i + 1 < len(lines) else "M runtime error"
            out.append(f"{file_label}:{current_line}: error: [{ecode.group(1)}] {message}")
            i += 2
            continue
        i += 1
    return out


def main() -> None:
    mode = sys.argv[1]
    candidate_path = sys.argv[2]
    timeout_s = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    source = Path(candidate_path).read_text()

    try:
        if mode == "parse":
            raw = run_instrumented(source, timeout_s)
            errors = extract_errors(raw, candidate_path)
            for line in errors:
                print(line, file=sys.stderr)
            sys.exit(1 if errors else 0)
        elif mode == "run":
            proc = run_raw(source, timeout_s)
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            sys.exit(proc.returncode)
        else:
            print(f"unknown mode {mode!r}, expected 'parse' or 'run'", file=sys.stderr)
            sys.exit(2)
    except EnvSetupError as exc:
        print(f"{candidate_path}:0: error: [ENVSETUP] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
