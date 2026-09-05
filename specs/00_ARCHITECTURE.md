# 00 — Architecture and shared contracts

**Every agent reads this file first.** It is the single source of truth for
interfaces between components. Nothing else in this repo may contradict it.

---

## 1. What the system is

A coding assistant for languages absent from model training data: COBOL, JCL,
AFSIM input decks, proprietary internal DSLs at primes and labs. The user
supplies a corpus (docs, example programs, expected outputs). The system
becomes a competent assistant for that language without fine-tuning and
without network egress.

**The differentiator is not retrieval. It is the verifier loop.** Generated
code is compiled or parsed by a real toolchain in a sandbox, errors are fed
back, and only verified output reaches the user. Say this in every context
where the project is described.

## 2. Process topology

Three processes on one machine. No network egress from any of them.

```
┌─────────────┐     ┌──────────────────────────┐     ┌──────────────┐
│   Ollama    │     │        HARNESS           │     │  MCP SERVER  │
│  (or vLLM)  │◄────┤  ashlar/harness/loop.py  ├────►│ ashlar/mcp/  │
│             │     │                          │     │              │
│ port 11434  │     │  the only component      │     │  stdio       │
│ OpenAI-     │     │  that talks to both      │     │  JSON-RPC    │
│ compatible  │     │  sides                   │     │              │
└─────────────┘     └────────────┬─────────────┘     └──────┬───────┘
                                 │                          │
                                 │ SSE / websocket          │ reads
                                 ▼                          ▼
                          ┌─────────────┐          ┌──────────────────┐
                          │  FRONTEND   │          │ corpus/ + *.db   │
                          │  (browser)  │          │ + sandbox runner │
                          └─────────────┘          └──────────────────┘
```

**Ollama never talks to the MCP server.** The harness is the wire. This is the
single most common misunderstanding about this design; correct it whenever you
see it in code comments or docs.

## 3. Repo layout

```
ashlar/
  __init__.py
  config.py            # loads config.yaml + corpora/<name>/meta.yaml
  ingest/
    __init__.py
    chunker.py         # doc → chunks
    indexer.py         # BM25 + optional embeddings
    symbols.py         # build symbol table from verifier + examples
  mcp/
    server.py          # the 5 tools. stdio entrypoint.
    sandbox.py         # container exec, no network, resource caps
  harness/
    loop.py            # generate → verify → repair
    model.py           # OpenAI-compatible client
    memory.py          # verified snippet cache + failure memory
    events.py          # event emitter consumed by frontend
  api/
    server.py          # FastAPI: SSE stream + POST /task, for frontend
corpora/
  plinth/
    meta.yaml
    docs/
    examples/
    pairs/
  cobol/
    meta.yaml
    docs/ examples/ pairs/
languages/
  plinth/              # the interpreter itself (a "toolchain", not part of ashlar)
    plinth/*.py
    pyproject.toml
frontend/
  index.html src/ ...
eval/
  runner.py
  cases/
prompts/
  system.md            # behavioral instructions, ~40 lines
  repair.md
config.yaml
TASKS.md
specs/                 # these documents
```

**Invariant:** nothing under `ashlar/` may reference `plinth` or `cobol` by
name. All language specifics come from `meta.yaml`.

## 4. `meta.yaml` contract

This file is what makes the system corpus-swappable. Every corpus has one.

```yaml
language: plinth
display_name: PLINTH
extension: .plth
comment_prefix: "#"

verifier:
  # {file} is substituted with an absolute path inside the sandbox.
  parse:   ["plinth", "parse", "--json", "{file}"]
  run:     ["plinth", "run", "--json", "{file}"]
  symbols: ["plinth", "symbols", "--json"]

sandbox:
  image: ashlar/plinth:latest
  timeout_s: 10
  memory_mb: 512

retrieval:
  bm25_weight: 0.75          # heavy: exact keyword match matters for DSLs
  embedding_weight: 0.25
  chunk_strategy: heading    # heading | fixed | blank_line
```

COBOL's version differs only in values (`cobc -x -free`, `.cbl`, image
`ashlar/cobol:latest`). If a new corpus needs a new *field*, that is a spec
change — flag it in `TASKS.md`.

### `verifier.symbols` is optional but high-value

If the toolchain can dump its own grammar (PLINTH can; `cobc` cannot), that
output is **ground truth** and outranks anything parsed from docs. For
toolchains without it, the symbol table is derived from parsing the example
corpus. See `02_BACKEND.md`.

## 5. Verifier result contract

Every verifier invocation, for every language, normalizes to this shape. The
sandbox layer is responsible for the normalization; adapters live in
`ashlar/mcp/sandbox.py`.

```json
{
  "ok": false,
  "errors": [
    {
      "file": "candidate.plth",
      "line": 14,
      "col": 9,
      "code": "E041",
      "message": "dimensional mismatch: field 'altitude' expects length, got speed (mps)",
      "severity": "error"
    }
  ],
  "warnings": [],
  "stdout": "",
  "stderr": "",
  "exit_code": 1,
  "duration_ms": 84
}
```

Rules:
- `ok` is `true` **only** when `errors` is empty and `exit_code == 0`.
- `line` is 1-indexed. `col` may be `null` if the toolchain doesn't report it.
- `code` may be `null` for toolchains without error codes. PLINTH always sets it.
- Unparseable verifier output → `ok: false` with a single synthetic error
  `code: "EHARNESS"`. Never silently pass.

## 6. MCP tool contracts

Five tools. Exact signatures. Do not add tools without a spec change; do not
add per-topic tools — see §7.

```python
lookup_symbol(name: str) -> dict
grep_corpus(pattern: str, limit: int = 20, kind: str = "all") -> list[dict]
get_examples(symbol: str, n: int = 3) -> list[dict]
read_file(path: str, start: int = 1, end: int = -1) -> dict
verify(source: str, run: bool = False, stdin: str = "") -> dict
```

Returns:

```json
// lookup_symbol("altitude")
{
  "found": true,
  "name": "altitude",
  "kind": "attribute",
  "valid_parents": ["platform", "waypoint"],
  "arg_shape": "<number:length>",
  "dimension": "length",
  "required": false,
  "doc_anchor": "docs/manual.md#platform-attributes",
  "example_refs": [{"file": "examples/coastal.plth", "line": 12}],
  "source": "verifier"        // verifier | examples | docs
}

// grep_corpus("inherit from", limit=5)
[
  {
    "file": "examples/patrol_pair.plth",
    "line": 21,
    "text": "  inherit from uav_01",
    "context_before": ["define platform uav_02 type air"],
    "context_after": ["  set altitude = 2200 m"],
    "kind": "example"          // doc | example | pair | cache
  }
]

// get_examples("inherit", n=2)
[
  {
    "file": "examples/patrol_pair.plth",
    "start": 20, "end": 24,
    "text": "define platform uav_02 type air\n  inherit from uav_01\n...",
    "verified": true
  }
]

// read_file("docs/manual.md", 40, 80)
{"file": "docs/manual.md", "start": 40, "end": 80, "text": "...", "truncated": false}

// verify(source, run=True) -> the §5 verifier result contract, verbatim
```

Error handling: a tool never raises to the model. On failure return
`{"error": "<message>"}` and let the harness decide.

### Tool docstrings are prompt engineering

The model sees only the docstring. Write them as instructions, not
descriptions. Required wording, keep or improve but don't neuter:

- `lookup_symbol`: "Confirm a symbol exists and where it is legal. Call this
  before emitting any identifier you are not certain about."
- `verify`: "Compile/parse candidate source in a sandbox. Never return code to
  the user that has not passed this."

## 7. Why five tools is enough — read before proposing more

The tools are **generic primitives parameterized by argument**, not per-topic
endpoints. `grep_corpus("average sensor")` needs no "average" handler; it is
regex over the corpus. One tool answers unbounded questions because the
argument varies, not the tool.

Knowledge scales in **data** — the corpus and the symbol table — not in code.
A new language is a folder. A 5,000-symbol language uses the same
`lookup_symbol` as a 50-symbol one.

Compare Claude Code: grep, read, edit, bash. Four tools, every codebase ever
written.

The only legitimate reason to add a tool is a genuinely new *kind of action*.
Realistic ceiling is eight. Candidates, in priority order if needed:
`run_case` (already folded into `verify(run=True)`), `check_semantics` for
validation the toolchain misses, `list_corpus_tree` for orientation.

## 8. Harness event contract

The harness emits events; the API server relays them over SSE; the frontend
renders them. Adding fields is fine, renaming is not.

```json
{"type": "task_start",   "task_id": "t_01", "prompt": "...", "ts": 0}
{"type": "tool_call",    "tool": "grep_corpus", "args": {...}, "ts": 120}
{"type": "tool_result",  "tool": "grep_corpus", "hits": 4, "preview": [...], "ts": 180}
{"type": "model_start",  "iteration": 1, "ts": 900}
{"type": "model_token",  "text": "define ", "ts": 940}
{"type": "model_done",   "iteration": 1, "source": "...", "ts": 3200}
{"type": "verify_start", "iteration": 1, "ts": 3210}
{"type": "verify_result","iteration": 1, "ok": false, "errors": [...], "ts": 3290}
{"type": "repair_start", "iteration": 2, "fixing": ["E041@14"], "ts": 3300}
{"type": "cache_hit",    "key": "...", "ts": 60}
{"type": "run_output",   "stdout": "...", "stderr": "...", "ok": true, "ts": 8050}
{"type": "task_done",    "task_id": "t_01", "ok": true, "iterations": 3,
                         "source": "...", "citations": [...], "ts": 8100}
{"type": "task_failed",  "task_id": "t_01", "reason": "max_iterations",
                         "last_errors": [...], "ts": 21000}
```

`run_output` (added after the initial build): once a candidate compiles clean, the harness runs it for real (`verify(source, run=True)`) purely so the UI can show the program's actual execution output, not just "it parsed" — a terminal/output panel showing this is what makes "verified" mean something concrete rather than an abstract pass/fail. Emitted once per successful task, right before `task_done`, whether or not a behavioral pair exists for that prompt (if one does, the same run also drives the existing expected-output diff in §9 step 7 — one call, two purposes, not two calls).

`ts` is milliseconds since `task_start`.

## 9. The loop, normatively

```
1. cache lookup on normalized task text        → if hit, verify and return
2. harness calls grep_corpus(task keywords)    ← deterministic, not model-chosen
3. harness calls get_examples(top symbols)     ← deterministic
4. model generates candidate                   ← the only creative step
5. verify(candidate)
6. if not ok and iteration < MAX_ITER (4):
     append errors + relevant symbol lookups, goto 4
7. if ok and a pair exists: verify(run=True), diff against expected
     mismatch → goto 4 with the diff
8. write verified source to cache + failure log
9. return with citations
```

**Steps 2, 3, 5 and 7 are harness-driven, not model-driven.** Local
open-weight models are unreliable at multi-turn tool selection; taking that
decision away from the model is the difference between a demo that works and
one that stalls. The model may *additionally* call tools, and that is
supported, but the deterministic pre-fetch always happens.

`MAX_ITER = 4`, configurable, surfaced in the UI.

## 10. Model layer

Everything speaks OpenAI-compatible `/v1/chat/completions`. Deployment target
is a base URL and a model name.

```yaml
model:
  base_url: http://localhost:11434/v1
  name: <chosen-model:tag>
  api_key: ollama         # ignored by Ollama, some clients require presence
  temperature: 0.1
  max_tokens: 2048
```

- Ollama for laptop and demo. vLLM for real GPU deployment — say this when
  officials ask, it is the answer they expect.
- Cloud endpoint permitted **for development only**, and every eval run records
  which endpoint produced it.
- Model choice is deliberately not fixed in this spec. Benchmark two or three
  current open-weight coding models on `eval/` and record the winner in
  `TASKS.md`. Do not hardcode a model name anywhere but `config.yaml`.

## 11. Learning, stated honestly

No fine-tuning. No weight updates. Two mechanisms, both data-only:

1. **Verified snippet cache** — every compile-clean solution is written back
   into the corpus index with its task text. Retrieval hits it next time.
2. **Failure memory** — every verifier error and the edit that resolved it is
   logged. The top recurring errors for the language are injected into the
   system context.

Also re-derive the symbol table after each accepted solution so user-defined
identifiers become known.

When describing this externally: "verified snippet cache and failure memory,
no weight updates, nothing leaves the machine." Do not say "self-improving" or
"continuously learning" without that qualifier. The honest version is more
persuasive to this audience than the inflated one, and it survives scrutiny.

## 12. Security posture — this is a product feature, build it in

- No network from sandbox containers. `--network=none`.
- No network from the MCP server or harness except the configured model base URL.
- Corpus never leaves disk. No telemetry. No analytics.
- Sandbox: read-only rootfs, tmpfs workdir, memory cap, wall-clock cap, non-root user.
- Demo must survive **wifi turned off**. Test this explicitly before the event.

## 13. Non-goals

- Not a VS Code extension. MCP server + web UI. Harness-agnostic is a
  stronger architectural claim than a bespoke editor plugin.
- Not a fine-tuning pipeline.
- Not multi-user. Single-seat, one process per user.
- Not an inference stack. Ollama/vLLM already solved that.
