# XenoScript

**An AI coding assistant for languages no model has ever seen.**

Give it a language's docs, example code, and a real toolchain to check
against, and it becomes a verified-output coding agent for that language —
running entirely offline, with no fine-tuning and no training data for the
language required.

The lead demo is **MUMPS (M)**, the language still running most of the
world's electronic health record systems (Epic, VistA, Meditech). It is
decades old, has almost no public documentation, and no mainstream AI
assistant can write it reliably. XenoScript can, because it never returns
code it hasn't actually compiled and run first.

## The idea

No model was trained on your internal DSL, your site's COBOL dialect, or the
undocumented scripting language behind your EHR. XenoScript doesn't try to
fix that by training a bigger model — it wraps whatever local model you
already have in a loop that:

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

| Corpus | Real toolchain | Status |
|---|---|---|
| `mumps` | [Reference Standard M](https://github.com/Reference-Standard-M/rsm) | Primary demo — globals, `FOR`/`IF`, `$SELECT`, `$JUSTIFY`/`$TRANSLATE`/`$FIND`, more |
| `cobol` | `cobc` (GnuCOBOL) | Working, smaller example set |
| `plinth` | — | Synthetic language, original architecture-proof corpus |

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

## Known limitations (documented honestly, not swept under the rug)

- **MUMPS output capture through the live backend server is unreliable.**
  The exact same generated code that prints correctly when run directly
  against the real interpreter can come back with empty captured stdout
  when driven through the long-running API server process. Root cause not
  fully isolated (see `LOG.md`). Workaround in place: the demo proves
  execution via the standalone terminal projects above, not the sidebar's
  own output panel.
- **The verified-solution cache can only catch runtime/syntax errors, not
  semantic correctness.** A structurally wrong but syntactically valid
  statement can pass verification and get cached as a "real example" for
  future similar prompts. Mitigated with a stricter cache similarity floor
  and a numeric-literal mismatch guard (`ashlar/harness/memory.py`), but the
  underlying gap — no behavioral check for tasks with no observable output
  — is real and unresolved.
- **Compound, multi-step prompts** ("delete X and confirm it's gone") tend
  to make the model invent non-existent syntax rather than compose two real
  statements. Keep prompts to one clear action.

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
