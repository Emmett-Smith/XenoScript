#!/usr/bin/env bash
# Compile-then-execute wrapper for GnuCOBOL, which has no single
# compile-and-run invocation (cobc is compile-only). meta.yaml's
# verifier.run points here. The sandbox always runs commands with
# cwd = repo root, so this relative path resolves correctly from there.
set -e
out="$(mktemp -d)/prog"
cobc -x -free -o "$out" "$1"
"$out"
