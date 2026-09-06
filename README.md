# XenoScript

**An AI coding assistant for classified, undocumented, and offline-only
languages.**

Every branch, agency, and prime contractor has internal DSLs and mission
languages that can't leave a secure room: no public documentation (because
they can't be public), no training data for any model, and no cloud AI tool
allowed anywhere near the environment. XenoScript is built for exactly that
case. Give it a language's docs, example code, and a real toolchain to check
against, and it becomes a verified-output coding agent for that language —
running **entirely offline, air-gapped, with no fine-tuning and no training
data for the language required.** Nothing it produces is ever shown to you
before it has actually been compiled or run against the real toolchain.

We can't put a classified language on a public repo, so this project proves
the same property two other ways instead: on **two real, publicly-known
undocumented legacy languages** (MUMPS and COBOL, below), and on **a
synthetic language we invented from scratch** (Plinth) specifically to
prove zero memorization mathematically — the exact property that matters
for a language no model could possibly have seen, classified or otherwise.
None of the three are the point on their own; the architecture that works
identically across all three is.

## The idea

No model was trained on your program's internal DSL, and none ever will be
— it's classified, it's proprietary, or it just never left the building.
XenoScript doesn't try to fix that by training a bigger model, sending code
to a cloud API, or hoping a model "figures it out." It wraps whatever local
model you already have in a loop that:

1. **Retrieves** real symbols, examples, and doc snippets from the
   language's own corpus — never invented, always grep'd from real files.
2. **Generates** a candidate solution.
3. **Verifies** it against a real toolchain (a real compiler, or a real
   interpreter like Reference Standard M) — not a guess, an actual parse/run.
4. **Repairs** automatically on failure, feeding the real error back to the
   model, up to a few attempts.
5. **Caches** verified solutions so the same or similar task never has to be
   solved twice.

No unverified code is ever shown to the user. A failed first attempt that
gets caught and fixed automatically is the product working as intended, not
a bug.

## Architecture, in one paragraph

Three local processes: a model server (Ollama, running fully offline), an
MCP server exposing five generic search-and-verify tools over an ingested
corpus, and a harness that wires them into the generate → verify → repair
loop above. **Adding a new language means adding a `corpora/<name>/` folder
— docs, examples, and a toolchain adapter — not writing new code.** Nothing
under `ashlar/` is allowed to know which language it's talking to; that's a
hard invariant, checked in review.

```
corpora/<name>/
  docs/       real language reference material
  examples/   real, working snippets (used for retrieval + fallback symbol extraction)
  pairs/      task.txt + expected.txt — known-good behavioral test cases
  bin/        the real toolchain adapter (compiler/interpreter wrapper)
  meta.yaml   corpus-specific config (comment syntax, file extensions, etc.)
```

## Supported corpora

Three proof points, not three products. Each demonstrates the same
architecture handling a language the model can't have memorized — the two
real ones because they're old and undocumented, the synthetic one because
it didn't exist until this project invented it.

| Corpus | Real toolchain | Proves |
|---|---|---|
| `mumps` | [Reference Standard M](https://github.com/Reference-Standard-M/rsm) | A real, decades-old, near-undocumented language still in production (VA/Epic/Meditech) — globals, `FOR`/`IF`, `$SELECT`, `$JUSTIFY`/`$TRANSLATE`/`$FIND`, more |
| `cobol` | `cobc` (GnuCOBOL) | The architecture isn't MUMPS-specific — a second, unrelated real legacy language and toolchain, smaller example set |
| `plinth` | — | Zero memorization, provably: a language invented for this project, absent from any model's training data — the closest public stand-in for an actual classified DSL |

## Running it locally

Requires [Ollama](https://ollama.com) running locally with a model pulled
(see `config.yaml` for the model currently configured), and
[`uv`](https://docs.astral.sh/uv/) for Python dependency management.

```bash
# Backend: FastAPI + the generate/verify/repair harness
uv run python -m ashlar.api.server        # http://localhost:8000

# Frontend: the demo UI
cd frontend && npm install && npm run dev # http://localhost:5173
```

The active corpus is set in `config.yaml` (`corpus: mumps`) and can also be
switched live from the frontend's corpus dropdown without restarting the
backend.

### VS Code extension

`vscode-extension/` embeds the same frontend inside a VS Code sidebar
webview, themed to match the active editor theme, with a real **Insert into
editor** action so generated code lands directly in an open file.

### Standalone proof-of-persistence demos

`demo-mumps/` and `demo-cobol/` are real, independent projects (not wired to
the FastAPI backend) used to prove that AI-generated code actually persists
data across runs: generate a routine, save it, run it for real in a
terminal, then read the database back and see the change — sidestepping any
question about whether the sidebar's own output display can be trusted.

## Bugs found, and fixed (documented honestly, not swept under the rug)

Three real limitations were found during development, root-caused, and
fixed — not hidden after the fact:

- **MUMPS output capture through the live backend server was unreliable.**
  Root cause: the real interpreter's stdin reader silently discarded the
  final piped-in line whenever generated source didn't end in a trailing
  newline — exit 0, no error, no output. Fixed at the single point both
  code paths funnel through; verified 5/5 through the live server.
- **The verified-solution cache could self-poison.** A structurally-wrong
  but error-free generation could get cited as a "real example" for the
  next similar prompt, reinforcing the same mistake. Fixed by only citing
  solutions that were actually checked against real ground truth, not just
  "ran without crashing."
- **Compound, multi-step prompts** hit a genuine small-model limitation on
  one specific pattern (a two-space grammar rule the model kept getting
  wrong even when told the exact fix). Fixed by normalizing it
  mechanically before the model's source ever reaches the interpreter, with
  the correction flowing back through to what the user actually sees.

Full build history, every real bug found and fixed, and exact live-tested
prompts are in [`LOG.md`](LOG.md). The original architecture specs (written
before any code existed) are in [`specs/`](specs/), starting with
[`specs/00_ARCHITECTURE.md`](specs/00_ARCHITECTURE.md).

## Repo layout

```
ashlar/             backend: ingest, MCP tool server, harness loop, API
corpora/            per-language docs/examples/pairs/toolchain (the whole "add a language" surface)
frontend/           Vite + React + TS demo UI
vscode-extension/   VS Code sidebar wrapper around the same frontend
demo-mumps/         standalone terminal demo proving real persistence
demo-cobol/         same, for COBOL
eval/               baseline/eval harness and measured numbers
specs/              original architecture + build specs
LOG.md              full build log — every real bug, fix, and verified test result
```
