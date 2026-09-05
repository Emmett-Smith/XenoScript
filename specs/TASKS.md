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
- [x] `plinth` lexer + parser, `parse --json` matching contract §5
- [x] Error codes E001–E052 emitted with fix-naming messages
- [x] 5 examples parsing clean (enough to unblock backend)
- [x] `plinth run --json` with deterministic trace
- [x] `plinth symbols --json`, all 52 symbols
- [x] Remaining 10 examples (15 total)
- [x] Runtime codes E070–E072
- [x] Dockerfile → `ashlar/plinth:latest` (written, untested — no Docker
      on this machine; sandbox.mode=subprocess is what's actually exercised)

  225 tests passing. Merged into master in Phase 2; real end-to-end
  integration proved (ingest, MCP tools, sandbox, live model all against
  real corpora/plinth). See LOG.md.

### Backend (Emmett)
- [x] Stub verifier + `corpora/stub/meta.yaml` — **do this first, hour 1**
- [x] Config loader (`config.yaml` + `meta.yaml`)
- [x] Ingest: chunker, BM25 index
- [x] Symbol table with source precedence
- [x] MCP server, all 5 tools
- [x] Sandbox — subprocess fallback done and tested; container/`--network=none`
      path intentionally unimplemented tonight (pre-decided, see Orchestrator)

  Built in isolated worktree, 58/58 tests, real stdio MCP session exercised
  all 5 tools. Not yet merged — Phase 2. See `LOG.md` for the `mcp` package
  version pin that must carry through the merge.

### Harness (Emmett)
- [x] Model client, OpenAI-compatible, streaming
- [x] Deterministic pre-fetch
- [x] Generate → verify → repair loop, MAX_ITER=4
- [x] `prompts/system.md` + `prompts/repair.md`
- [x] Event emitter matching contract §8
- [x] FastAPI + SSE

  Built against `FakeToolClient`/`FakeModel` in an isolated worktree (no
  real MCP server yet). 59/59 tests green. Not yet merged/integrated —
  that's Phase 2. See `LOG.md`.

### Frontend (Partner, after 5 examples parse)
- [x] Vite scaffold, design tokens as CSS custom properties
- [x] `useTaskStream` reducer over the event union
- [x] Corpus panel — live tool calls
- [x] Code panel — streaming + error underline
- [x] Verifier panel — verdict block + attempt ledger
- [x] Prompt bar

  Built and actually exercised in a real browser against real fixtures +
  the real running API server (not just `npm run build` passing). Real
  Plex fonts vendored locally. Not verified: physical projector, explicit
  networking-disabled reload. See LOG.md.

### Eval (either)
- [x] 20 cases written (task.txt + rubric.yaml; behavioral expected.txt
      generated for real in Phase 2 by running solutions through the real
      interpreter — no more TODOs)
- [x] Runner with `--arm` (`--all-arms`, `--repeat`, provenance stamping)
- [x] **Arm A recorded** — 0% (0/20), live `qwen2.5-coder:3b`, consistent
      across two separate runs — the number the whole pitch rests on
- [x] Arm B recorded (long-context competitor) — 0-5% (varied run to run
      on unchanged code — see LOG.md), consistently slow (p50 30s+)
- [~] Arms C, D, E with `--repeat 3` — C=20% (4/20), D=25% (5/20), both
      `--repeat 1` on the SAME commit (apples-to-apples, after fixing a
      real bug where C's retrieval had silently drifted from D's — see
      LOG.md "the critical correction"). E needs cloud credentials this
      machine doesn't have. **`--repeat 3` not done for any arm** —
      observed run-to-run variance (B swung 5%→0% with zero code change)
      means this is a real gap, not a formality; exact command in the
      morning handoff.

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
- [x] Written failure analysis per `05_EVAL.md` §7 — `eval/FAILURE_ANALYSIS.md`

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

**Chosen model:** `qwen2.5-coder:3b` (3.1B, Q4_K_M, 32k ctx) — appeared on
`localhost:11434/api/tags` partway through the session (was empty at start).
**This is a re-probe finding, not a bake-off** — it's the only model that was
ever available tonight, so "benchmark 2-3 models" (P1) is still unrun. One
live smoke test passed end-to-end against `corpora/stub`. No eval score yet
(Phase 4).

---

## Notes and spec corrections

Append freely. Format: `- [component] what the spec got wrong, what you did.`

- [orchestrator] `ORCHESTRATOR.md`'s Phase 1 table names the package dir
  `xenoscript/`, but `00_ARCHITECTURE.md` #3 and `README.md` both specify
  `ashlar/`. Went with `ashlar/` (binding-contract doc wins). See `LOG.md`
  NEEDS HUMAN.
- [architecture] `meta.yaml`'s `sandbox:` block gained an optional `mode`
  field (`subprocess|container`), overriding `config.yaml`'s top-level
  `sandbox.mode`. Not in the #4 example, but explicitly requested by
  `ORCHESTRATOR.md` Phase 0 ("set it in config.yaml and in every meta.yaml").
- [backend] `pyproject.toml`'s unpinned `mcp>=1.0.0` resolves via `uv sync`
  to `mcp==2.1.1`, which renames `mcp.server.fastmcp.FastMCP` and breaks
  the exact import both `00_ARCHITECTURE.md` §6 and `02_BACKEND.md` §3
  specify verbatim. Pinned to `mcp>=1.0.0,<2.0.0` (resolves 1.29.1).
- [backend] `02_BACKEND.md`'s `run_verifier(source, mode, stdin="")`
  signature has no way to know which corpus/meta.yaml to use. Added
  optional `meta=`/`cfg=` keyword overrides (defaults load the active
  corpus from `config.yaml`), same pattern used in `ingest.pipeline`.
- [language] `01_LANGUAGE.md` §4's grammar shows `NEWLINE` after block
  headers, but §2 says whitespace is insignificant except as a token
  separator. Read as: newlines are non-significant; the parser recovers
  block structure from keyword shape + explicit `end_*` terminators.
- [language] §5.4's bare-integer exception clause is ambiguous
  ("count, priority, field_of_view multiplier and step subdivision... the
  subdivision case is tolerance"). Read as: bare integers legal for
  `priority`, `field_of_view`, `tolerance`; `step` always takes a time
  quantity; `count` isn't an attribute anywhere in the grammar so wasn't
  implemented.
- [phase2] Eval case 019 originally asked to halt a 20s scenario at 15s —
  unreachable by design (E070: halt must be at/after scenario duration).
  Found by actually running it through the real interpreter during Phase 2
  verification. Reworded to a 15s scenario halting at 15s.
- [phase2] `set position at ...` is not valid PLINTH syntax — `position`
  is a bare `position at <lat> <lon>` statement, not a `set`-assignment.
  Three of my own hand-written eval-case repair snippets (015-017) had
  this bug; found and fixed the same way, by running the real interpreter.
