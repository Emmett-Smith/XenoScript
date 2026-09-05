# TASKS — living board

**Every agent: read this at session start, update it at session end.** Check
boxes, and add a line under Notes for anything the specs got wrong. This file
is how parallel agents avoid duplicating and colliding.

Status key: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

---

## Critical path

The interpreter's `parse` command blocks `verify`, which blocks the harness
loop and the frontend's real data. **Everyone else builds against
`corpora/stub` until PLINTH lands.** Do not idle waiting.

```
stub verifier (1h, Emmett) ──┬──► harness loop ──► frontend
                             └──► MCP server
plinth parse (Partner, hours 1-4) ──► plinth run ──► plinth symbols
                                                       └──► real symbol table
eval arm A (2h, either) ──► arms B-E
```

---

## P0 — demo cannot happen without these

### Language (Partner)
- [ ] `plinth` lexer + parser, `parse --json` matching contract §5
- [ ] Error codes E001–E052 emitted with fix-naming messages
- [ ] 5 examples parsing clean (enough to unblock backend)
- [ ] `plinth run --json` with deterministic trace
- [ ] `plinth symbols --json`, all 52 symbols
- [ ] Remaining 10 examples
- [ ] Runtime codes E070–E072
- [ ] Dockerfile → `ashlar/plinth:latest`

### Backend (Emmett)
- [ ] Stub verifier + `corpora/stub/meta.yaml` — **do this first, hour 1**
- [ ] Config loader (`config.yaml` + `meta.yaml`)
- [ ] Ingest: chunker, BM25 index
- [ ] Symbol table with source precedence
- [ ] MCP server, all 5 tools
- [ ] Sandbox with `--network=none` + subprocess fallback

### Harness (Emmett)
- [ ] Model client, OpenAI-compatible, streaming
- [ ] Deterministic pre-fetch
- [ ] Generate → verify → repair loop, MAX_ITER=4
- [ ] `prompts/system.md` + `prompts/repair.md`
- [ ] Event emitter matching contract §8
- [ ] FastAPI + SSE

### Frontend (Partner, after 5 examples parse)
- [ ] Vite scaffold, design tokens as CSS custom properties
- [ ] `useTaskStream` reducer over the event union
- [ ] Corpus panel — live tool calls
- [ ] Code panel — streaming + error underline
- [ ] Verifier panel — verdict block + attempt ledger
- [ ] Prompt bar

### Eval (either)
- [ ] 20 cases written
- [ ] Runner with `--arm`
- [ ] **Arm A recorded** — the number the whole pitch rests on
- [ ] Arm B recorded (long-context competitor)
- [ ] Arms C, D, E with `--repeat 3`

### Demo
- [ ] Demo script written — **hour 1, before building**
- [ ] Offline run verified with networking disabled
- [ ] Screen recording of a successful run as insurance
- [ ] Rehearsed twice on a timer

---

## P1 — strongly improves the pitch

- [ ] COBOL corpus: `meta.yaml`, docs, 10 examples, 10 eval cases
- [ ] COBOL arms A–D recorded
- [ ] Verified snippet cache + reindex
- [ ] Failure memory + `top_failures` injection
- [ ] Cold vs warm cache comparison recorded
- [ ] Baseline chart in UI, reading from `/eval/latest`
- [ ] Corpus switcher, live, no restart
- [ ] Model bake-off: 2–3 current open-weight coding models, winner recorded below
- [ ] Written failure analysis per `05_EVAL.md` §7

---

## P2 — only if genuinely ahead

- [ ] Embeddings alongside BM25
- [ ] tree-sitter grammar for PLINTH
- [ ] Live-ingest rehearsal on two unfamiliar corpora
- [ ] Symbol re-derivation after accepted solutions
- [ ] `run_case` stdin support in eval rubrics

---

## Decisions log

Record choices here so agents stop re-litigating them.

| Date | Decision | Rationale |
|---|---|---|
| — | Synthetic language, not MATLAB | MATLAB is in training data; no measurable headroom |
| — | MCP server + web UI, not a VS Code extension | Harness-agnostic is a stronger claim; less UI work |
| — | Retrieval is harness-driven, not model-chosen | Local models are unreliable at multi-turn tool selection |
| — | Five MCP tools, fixed | Generic primitives; coverage scales in corpus, not code |
| — | No fine-tuning | Cannot demo a curve in 36h; cache + failure memory is the honest version |
| — | Model name lives only in `config.yaml` | Bake-off pending; keeps us vendor-neutral |

**Chosen model:** _pending bake-off — record name, tag, and eval score here_

---

## Notes and spec corrections

Append freely. Format: `- [component] what the spec got wrong, what you did.`

- 
