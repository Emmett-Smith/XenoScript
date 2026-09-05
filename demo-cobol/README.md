# demo-cobol — a real, standalone COBOL project

Real COBOL programs, compiled and run with the real GnuCOBOL compiler
(`cobc`) -- the same toolchain XenoScript's own verifier uses. No daemon, no
shared state to worry about (unlike the MUMPS demo next door): each run
just compiles the source into a fresh binary and executes it.

## Try it (from a VS Code integrated terminal, in this folder)

```bash
./run.sh programs/greeter.cbl     # HELLO, ASHLAR.
./run.sh programs/countup.cbl     # counts 1 to 4
./run.sh programs/tempcheck.cbl   # a threshold check
```

## Suggested VS Code setup

- Install a COBOL syntax highlighter (already done on this machine:
  `bitlang.cobol`) so the `.cbl` files below are readable.
- Open this folder as a workspace (or add it as a folder in a multi-root
  workspace alongside the main repo).
- Open an integrated terminal here and run the commands above directly.

## Prerequisite

GnuCOBOL, installed via `brew install gnucobol` if `cobc` isn't already
on your PATH.
