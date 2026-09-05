# demo-mumps — a real, standalone MUMPS project

This is a real, persistent MUMPS/M project, independent of the XenoScript
extension. Open this folder directly in VS Code, browse and run these
files yourself, and you can verify with your own eyes that XenoScript's
generated code runs against exactly the same real interpreter -- nothing
here is a mock or a canned demo.

## What it uses

[Reference Standard M (RSM)](https://github.com/Reference-Standard-M/rsm),
a real open-source implementation of ANSI M, already built at
`../.toolchains/rsm/bin/rsm` for this repo. Same binary XenoScript's own
verifier calls.

## Try it (from a VS Code integrated terminal, in this folder)

```bash
./run.sh routines/seed_patients.m     # creates db/hospital.dat, adds 2 patients
./run.sh routines/lookup_patient.m    # a SEPARATE process -- reads back what seed_patients wrote
./run.sh routines/add_patient.m       # adds a 3rd patient
./run.sh routines/list_patients.m     # shows all of them, still there
./run.sh routines/vitals_alert.m      # a self-contained example, no database needed
```

Each `./run.sh` call is a genuinely separate process. `lookup_patient.m`
sets nothing -- if it prints a real name, that record survived from an
earlier, unrelated run. That's the actual proof this is a real,
persistent database and not a script re-running itself.

## Why this database won't randomly reset

XenoScript's own verifier (used when you ask it to write MUMPS code) uses a
*different*, separate database at `../corpora/mumps/env/mumps.dat`, and
deliberately wipes every global before each check it runs, so one
generation task can never see another's leftover state. This project's
`db/hospital.dat` is a completely different file and is never touched by
XenoScript -- what you build here stays here.

## One real constraint worth knowing

Each MUMPS environment needs its own small slice of macOS's shared
memory, and the OS default ceiling is only 4 MiB total -- too small for
both this project's environment and XenoScript's own to run at once, out of
the box. If `./run.sh` reports `Unable to create shared memory segment`,
either raise the ceiling once:

```bash
sudo sysctl -w kern.sysv.shmmax=16777216 kern.sysv.shmall=4096
```

or stop whichever of the two (XenoScript's backend / this project) you're
not actively using.

## Suggested VS Code setup

- Install a MUMPS syntax highlighter (already done on this machine:
  `dsilin.mumps`) so the `.m` files below are readable, not plain text.
- Open this folder as a workspace (or add it as a folder in a multi-root
  workspace alongside the main repo).
- Open an integrated terminal here and run the commands above directly.
