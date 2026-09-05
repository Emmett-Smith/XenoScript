#!/usr/bin/env bash
# Compiles and runs a real COBOL program with the real GnuCOBOL compiler
# (the same toolchain Ashlar's own verifier uses) -- no daemon, no shared
# state, just: compile, then execute the resulting binary. Usage:
#   ./run.sh programs/greeter.cbl
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v cobc >/dev/null 2>&1; then
  echo "cobc not found -- install GnuCOBOL first: brew install gnucobol" >&2
  exit 1
fi

if [ $# -eq 0 ]; then
  echo "Usage: $0 <program.cbl>" >&2
  exit 1
fi

out="$(mktemp -d)/program"
cobc -x -free -o "$out" "$1"
"$out"
