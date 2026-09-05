#!/usr/bin/env bash
# Runs a real M routine against a real, persistent Reference Standard M
# database -- this is the same open-source interpreter Ashlar's own
# verifier uses (see ~/XenoScript/.toolchains/rsm), pointed at a
# standalone volume that's yours to keep, browse, and build on. Unlike
# Ashlar's internal verifier (which wipes every global before each check,
# on purpose, so one task can never see another's leftover state), this
# database really does persist between runs -- that's the point: set a
# patient record in one run, read it back in a completely separate one.
#
# Usage: ./run.sh routines/patient_lookup.m
set -euo pipefail
cd "$(dirname "$0")"

RSM="../.toolchains/rsm/bin/rsm"
DB="db/hospital.dat"

if [ ! -x "$RSM" ]; then
  echo "rsm binary not found at $RSM -- build it first: see ../corpora/mumps/bin/rsm_run.py's" >&2
  echo "module docstring, or just: cd .. && git clone https://github.com/Reference-Standard-M/rsm && cd rsm && make" >&2
  exit 1
fi

if [ ! -f "$DB" ]; then
  echo "Creating a new database volume at $DB ..." >&2
  "$RSM" -v HOSPITAL -b 4 -s 500 "$DB"
fi

# Idempotent start: if the environment is already up (from an earlier
# run.sh call, or because Ashlar's own server raised the shared-memory
# ceiling this session), this just no-ops instead of erroring.
if ! "$RSM" -x 'QUIT' "$DB" >/dev/null 2>&1; then
  echo "Starting the environment ..." >&2
  "$RSM" -j 4 "$DB"
fi

if [ $# -eq 0 ]; then
  echo "Usage: $0 <routine.m>" >&2
  exit 1
fi

"$RSM" "$DB" < "$1"
