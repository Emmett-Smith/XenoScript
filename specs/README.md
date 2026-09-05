# Project Ashlar — spec set

Working name: **Ashlar**. A coding assistant for languages no model has seen.
Drop in documentation, example code, and expected outputs. Get a verified-output
coding agent for that language, running fully offline.

## Read order for agents

| Doc | Owner | Read when |
|---|---|---|
| `00_ARCHITECTURE.md` | everyone | **First. Always.** Contains the interface contracts. |
| `01_LANGUAGE.md` | Partner | Building the synthetic language + interpreter + corpus |
| `02_BACKEND.md` | Emmett | Building ingest, symbol table, MCP server |
| `03_HARNESS.md` | Emmett | Building the agent loop and model layer |
| `04_FRONTEND.md` | Partner (after 01) | Building the demo UI |
| `05_EVAL.md` | either | Building the eval harness and baseline numbers |
| `06_DEMO.md` | both | Last two hours |
| `TASKS.md` | everyone | Every session start and end |

## Rules for agents working on this repo

1. **Read `00_ARCHITECTURE.md` before touching code.** It defines every
   cross-component interface. If your change would alter one of those
   contracts, stop and flag it rather than editing unilaterally — another
   agent is coding against it right now.
2. **Update `TASKS.md` when you finish something.** Check the box, add a
   one-line note on anything you discovered that the spec got wrong.
3. **Never break the corpus-agnostic invariant.** No language-specific logic
   in `ashlar/` — that all lives in `corpora/<name>/meta.yaml`. If you find
   yourself writing `if language == "plinth"`, you have made a mistake.
4. **Verified output only.** No code path returns unverified source to the
   user. This is the product; treat it as a hard invariant.
5. **Every claim in the demo needs a number behind it.** If you add a
   capability, add its eval case in the same PR.

## Two-sentence version, for anyone joining

Three local processes: a model server (Ollama), an MCP server exposing five
generic search-and-verify tools over an ingested corpus, and a harness that
wires them into a generate → compile → repair loop. Adding a language means
adding a corpus folder, not code.
