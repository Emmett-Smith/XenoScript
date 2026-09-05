# LOG

## Session 2026-09-05 — autonomous overnight build (lead agent)

Human asleep. Operating per `specs/ORCHESTRATOR.md`. No questions asked;
ambiguities resolved below and work continues.

### Environment probe (§2)

```
python3 --version   → Python 3.13.14   (>=3.11 OK)
node --version       → v22.18.0
npm --version        → 11.5.2
curl localhost:11434/api/tags → {"models":[]}   -- Ollama up, no models yet (expected: user mid-download of qwen2.5-coder:3b)
git rev-parse --is-inside-work-tree → true
docker                → not probed (pre-decided: sandbox.mode=subprocess only, per Orchestrator §2/Phase 0)
uv                    → available at /opt/homebrew/bin/uv (will use for Python env/deps)
pip show mcp          → 1.28.1 already installed
pip show openai/fastapi/rank_bm25 → not installed, will add via uv
```

Adaptation: No live model tonight at session start. Building FakeModel fixture
path per instructions. Will re-probe `localhost:11434/api/tags` at the start
of each phase; if qwen2.5-coder (or any model) appears, will record exact
name:tag in TASKS.md "Chosen model" and switch arms A-E / live loop to use it.

### Decisions / ambiguity resolutions (autonomy policy §4)

1. **Package name: `ashlar/` not `xenoscript/`.** `specs/00_ARCHITECTURE.md`
   §3 (the binding contract doc) and `specs/README.md` both specify repo
   layout `ashlar/...`. `specs/ORCHESTRATOR.md`'s Phase 1 dispatch table says
   `xenoscript/`. This is a genuine contradiction between two spec docs
   (repo folder itself happens to be named `XenoScript`, likely a leftover
   working title). Resolving per §4 rule "pick the reading most consistent
   with 00_ARCHITECTURE.md": using `ashlar/` everywhere. Noted under NEEDS
   HUMAN below for visibility, not blocking.
2. Project display name / product name: "Ashlar" per README.md line 3 (and
   00_ARCHITECTURE §3 package name). Using this in docstrings, MCP server
   name, prompts, frontend header.
3. Solo session — TASKS.md assigns work to "Emmett" and "Partner" as a
   two-person team; tonight it's just me as lead + subagents. Treating all
   P0 items across both owners as in-scope, dispatched via subagents per
   Phase 1/3 of the Orchestrator.
4. Sandbox: `subprocess` mode only tonight, per explicit pre-decision. No
   Docker path implemented, only stubbed with `NotImplementedError` so the
   interface stays honest (per Phase 0 instructions).
5. Model bake-off (00_ARCHITECTURE §10, TASKS.md P1): cannot run tonight,
   no model loaded. Leaving `config.yaml` model name as a placeholder
   pointing at whatever `ollama list` reports once available, documented in
   handoff.

## NEEDS HUMAN

- `xenoscript/` vs `ashlar/` naming contradiction between ORCHESTRATOR.md and
  00_ARCHITECTURE.md/README.md (see decision #1 above). Went with `ashlar/`.
  Flag if that's wrong — a global rename is mechanical if so.
- Model bake-off (TASKS.md "Chosen model") is unrun — no model was loaded
  during this session's window. See morning handoff for the exact commands.

### Session plan (written before dispatching anyone)

- Phase 0 (me, ~45 min): repo skeleton, config loader, `corpora/stub`,
  `scripts/check.sh`, trivial pytest. Commit.
- Phase 1 (3 parallel subagents, ~3h budget): `language` (PLINTH interpreter
  + corpus), `backend` (ingest/symbols/MCP/sandbox), `harness` (loop/model/
  prompts/API). Disjoint directories per Orchestrator table.
- Phase 2 (me, ~1h): integration — stub→plinth corpus swap, FakeModel
  fail-then-repair fixture run, verify repair path engages, full event log.
- Phase 3 (1 subagent, ~2h): frontend against recorded Phase 2 event fixtures.
- Phase 4 (me, ~1.5h): 20 eval cases, runner with --arm/--repeat, run against
  FakeModel since no live model; document exact command for arms A-E for the
  morning.
- Phase 5 (me, remaining time): Pass A verification (exercise every DoD box
  honestly), then Pass B improvements ranked by demo impact per hour.
- Write MORNING HANDOFF at top of this file before stopping.

---

### Phase 0 — done (commit d02dd37)

- `ashlar/` skeleton (config, ingest, mcp, harness, api packages), `ashlar/config.py`
  loads `config.yaml` + `corpora/<name>/meta.yaml` into dataclasses — this is the
  shared interface Phase 1's three subagents will import.
- `corpora/stub/meta.yaml` + `corpora/stub/verifier.py`: 00_ARCHITECTURE §5-compliant,
  returns ok unless source contains literal `FAIL` (fabricated E041 at line 3).
- `pyproject.toml` + `uv sync`: mcp, openai, fastapi, uvicorn, rank-bm25, pyyaml,
  sse-starlette, pytest, ruff. Used `uv` since no venv existed and it was already
  on the machine (faster than pip).
- `scripts/check.sh`: ruff + pytest + grep assertion that `ashlar/` never says
  `plinth`/`cobol` outside tests. All green.
- Extended `meta.yaml`'s `sandbox:` block with a `mode` field (subprocess|container,
  optional, overrides `config.yaml`'s top-level `sandbox.mode`) per ORCHESTRATOR
  Phase 0's explicit instruction to pre-decide subprocess mode in every meta.yaml.
  Noting this as an intentional, instructed spec extension (00_ARCHITECTURE §4 asks
  new fields be flagged in TASKS.md — done there too).
- Container sandbox path intentionally NOT built tonight — backend agent will stub
  it with `NotImplementedError` so the interface stays honest, per instructions.

Dispatching Phase 1 now: language, backend, harness subagents in parallel,
disjoint directories. Each in its own git worktree (avoids concurrent
`git commit` lock races on the shared repo since all three run at once).

**Model server update:** a model appeared mid-session —
`qwen2.5-coder:3b` (3.1B, Q4_K_M, 32k ctx, tools-capable). Confirmed via
`curl localhost:11434/api/tags` at the time the harness agent reported.
Recorded in `config.yaml` and `specs/TASKS.md` "Chosen model" by the
harness agent. **This is a re-probe finding, not a real bake-off** — only
one model was ever available tonight, so the "benchmark 2-3 models" item
in `00_ARCHITECTURE.md` #10 / TASKS.md P1 remains unrun. Left in handoff.

### Phase 1 — harness agent: done

Worktree `/Users/owner/XenoScript/.claude/worktrees/agent-a0dc2128f296264cd`
branch `worktree-agent-a0dc2128f296264cd`, 11 commits, 59/59 tests passing,
`./scripts/check.sh` green in that worktree.

Built: `ashlar/harness/{model,prompts,tool_client,subprocess_verify,keywords,
repair,events,memory,loop}.py`, `ashlar/api/server.py`, `prompts/{system,repair}.md`,
`eval/offline_check.py`. Full event contract sequence verified against a
fail-then-succeed `FakeModel` fixture — matches `00_ARCHITECTURE.md` §8
exactly. Cache-hit re-verify, history-not-accumulated-verbatim, MAX_ITER,
task budget, and offline (zero non-loopback socket connects) all tested green.

**ToolClient interface** (the plug point for backend's real MCP client in
Phase 2):
```python
class ToolClient(Protocol):
    def lookup_symbol(self, name: str) -> dict: ...
    def grep_corpus(self, pattern: str, limit: int = 20, kind: str = "all") -> list[dict]: ...
    def get_examples(self, symbol: str, n: int = 3) -> list[dict]: ...
    def read_file(self, path: str, start: int = 1, end: int = -1) -> dict: ...
    def verify(self, source: str, run: bool = False, stdin: str = "") -> dict: ...
```
`HarnessDeps.tool_client` is the single field to swap; `ashlar/api/server.py`'s
`_build_tool_client(meta)` is the single server-side function to change.

**Notable live-model finding, not a bug, flagging for eval/Phase 5:** with
`qwen2.5-coder:3b` and no `tools` param wired, the model emitted a
hallucinated tool-call-shaped string as its "source" on the one live smoke
test, and it happened to pass only because the stub verifier merely checks
for the literal `FAIL`. This is exactly the weak multi-turn-tool-orchestration
failure mode the deterministic-pre-fetch design exists to route around
(00_ARCHITECTURE §9) — once the real PLINTH verifier is wired in Phase 2,
confirm this kind of malformed "source" gets a real parse error (E001/E003),
not a false pass. Worth an explicit test.

**Spec ambiguities resolved by the harness agent** (my read: all reasonable,
adopting as-is): repair context window read as 3-before+3-after (7 lines)
rather than "line + 3" total; added a `{current_source}` placeholder to
`repair.md` since the loop narrative requires resending current source but
the §3 skeleton had no slot for it; `run_task` takes an explicit `HarnessDeps`
param instead of implicit globals (testability, no behavior change).

**Known gap, honest:** no real MCP server to integrate against yet (backend
still running) — stood in with `FakeToolClient` + a subprocess helper that
shells out to the real `corpora/stub/verifier.py`. Corpus-switch logic is
generic but only exercised against one corpus so far.

Still waiting on `language` and `backend` agents before Phase 2 integration.

### Phase 1 — backend agent: done

Worktree `/Users/owner/XenoScript/.claude/worktrees/agent-afa13be4cc4c0f07d`
branch `worktree-agent-afa13be4cc4c0f07d`, 5 commits (on top of Phase 0),
58/58 tests, ruff clean, zero `plinth`/`cobol` under `ashlar/` incl. tests.

Built: `ashlar/mcp/sandbox.py` (`run_verifier`, subprocess-only, container
raises `NotImplementedError` as instructed), `ashlar/ingest/{chunker,indexer,
symbols,pipeline,__main__}.py`, `ashlar/mcp/server.py` (all 5 tools), plus
fixture content under `corpora/stub/{docs,examples,pairs}`. Exercised all
5 MCP tools via a real stdio JSON-RPC session (not just direct calls) —
transcript in the agent's full report. `read_file` path-traversal and
`grep_corpus` bad-regex both return clean error dicts, tested.

**Important dependency finding, must survive the merge:** `uv sync`
resolves `mcp>=1.0.0` to `2.1.1`, which renames
`mcp.server.fastmcp.FastMCP` and breaks the exact import
`00_ARCHITECTURE.md` §6 / `02_BACKEND.md` §3 specify verbatim. Backend
pinned `mcp>=1.0.0,<2.0.0` in `pyproject.toml` (resolves to 1.29.1) in its
worktree. **Action for me at merge time:** apply this same pin to the
merged `pyproject.toml`, re-`uv sync`, and confirm the harness agent's
code (which may reference `mcp` types too) still imports clean under 1.x.

**Backend's symbol-precedence reading** (adopting as-is): exactly one tier
is authoritative per corpus — verifier if `meta.yaml` defines the
`symbols` command, else parsed-examples, else docs — every other tier may
only enrich (`doc_anchor`, `example_refs`), never introduce new rows or
overwrite `source`. Chosen specifically so "52 PLINTH symbols, all
source=verifier" is achievable exactly once, not polluted by scraping.
Matches the spec's stated intent in `02_BACKEND.md` §2.

**Noted oddity, not backend's bug:** the Phase-0 stub verifier's JSON
payload self-reports `exit_code: 1` on failure but the script never calls
`sys.exit()`, so the real process exit code is 0. Backend's sandbox
correctly derives `ok` from `errors`/actual `proc.returncode`, not the
payload's self-reported field — this is arguably a hardening improvement,
not a bug, since it protects against a lying toolchain. Leaving the stub
as-is (it's disposable) but the "never trust self-reported exit_code
alone" lesson should carry into the real PLINTH sandbox invocation too.

**`verifier.symbols` output schema** — inferred (`01_LANGUAGE.md` was out
of backend's scope), needs a quick cross-check against the language
agent's actual `plinth symbols --json` output at merge time.

Still waiting on `language` agent before Phase 2 integration.

### Phase 1 — language agent: done

Worktree `/Users/owner/XenoScript/.claude/worktrees/agent-a2c4d55469a27a10d`
branch `worktree-agent-a2c4d55469a27a10d`, 8 commits, 225 tests passing.

Full PLINTH vertical: lexer/parser/checker/runtime/symbols sharing one
`grammar.py` constants module (so `symbols --json` can't drift from what
the checker enforces), 15 examples, 15 pairs, docs with the deliberate
gaps, 23 error-code fixtures, golden traces for all 15 examples. Dockerfile
written but untested (no Docker on this machine, as expected).

**Resolved ambiguities I'm adopting as-is:** newlines non-significant
(parser recovers structure from keywords + explicit `end_*` terminators,
not `NEWLINE` tokens); `mount` implemented as `bind mount <- <platform>`
(matches the architecture doc's own trace example verbatim); strict
declaration-before-reference on every plain identifier reference, `bind`
as the sole forward-reference escape hatch; §5.4's bare-integer exception
read as `priority`/`field_of_view`/`tolerance` (not `step`, which always
takes a time quantity); first-error-wins rather than accumulating a list.

### Phase 1 complete. Starting Phase 2 (integration, done personally).

All three branches merged into master (`d02dd37`..`5b8161e`, one trivial
`pyproject.toml` conflict on the already-identical `mcp` pin, one
`specs/TASKS.md`/`uv.lock` conflict on the harness agent's own
"Chosen model" note -- kept the equivalent text already on master,
regenerated `uv.lock` fresh rather than hand-merging it). Full suite green
post-merge: 112 ashlar/eval tests, 225 language tests.

**The real integration proof, not just merged code:**

- `corpora/stub` → `corpora/plinth` swap confirmed as a genuine one-line
  `config.yaml` change (`corpus: stub` → `corpus: plinth`) -- no code
  touched. `python -m ashlar.ingest --corpus corpora/plinth`: 52 symbols
  (all `source=verifier`), 15 examples/445 lines, 15 pairs, 27 doc chunks,
  0.34s. Zero `solution.plth` leakage into the index (checked directly).
- Real MCP server exercised via a real stdio JSON-RPC session against the
  real PLINTH corpus (not just direct function calls this time):
  `lookup_symbol`, `grep_corpus`, `verify` all correct.
- Real sandbox → real interpreter, both paths: a deliberately broken
  `1500 m` source returns the exact fix-naming E043 message from
  `01_LANGUAGE.md`; the fixed version passes. `verify(source, run=True)`
  against a real `corpora/plinth/pairs/001/solution.plth` produces a
  byte-exact match against its `expected.txt`.
- **The actual Phase 2 exit criterion**: wrote
  `scripts/phase2_integration_smoke.py` -- one task, real PLINTH corpus,
  `FakeModel` scripted to fail iteration 1 (real E043) then succeed
  iteration 2, full event stream asserted against the §8 contract and
  written to `eval/fixtures/event_streams/phase2_fail_then_repair.jsonl`
  for the frontend agent to use as a Phase 3 fixture. Passes.
- **Live corpus switching, twice in a row, no restart**: drove the actual
  FastAPI app (not a mock) through `stub → plinth → stub → plinth` via
  `POST /corpus/switch`, confirming `tool_client` and `Corpus.symbol_names`
  genuinely re-point each time (52 symbols under `plinth`, 0 under `stub`,
  correctly, every time). This is one of the four invariants the morning
  handoff needs to confirm -- confirmed, ahead of Phase 5.
- **One live task through the real model**: `qwen2.5-coder:3b` → real
  PLINTH → real sandbox, end to end, 6.7s, `ok=True` in 2 iterations.

**Architecture gap found and fixed:** the harness agent's
`_build_tool_client`/`AppState.switch_corpus` (built without a real MCP
server available in their worktree) hardcoded `Corpus(symbol_names=[],
pairs={})` and used a `FakeToolClient` wrapping only the subprocess
verifier -- `lookup_symbol`/`grep_corpus`/`get_examples` returned nothing
through the API even once real data existed. Also, `ashlar/mcp/server.py`
bound its corpus at import time with no way to repoint it, which would
have made `POST /corpus/switch` a lie for the MCP tools specifically (the
API's own bookkeeping would update; what the tools actually returned
would not). Fixed: `ashlar/mcp/server.py` gained `set_active_corpus()`;
`ashlar/mcp/client.py`'s new `RealToolClient` calls through to the real
tool functions; `Corpus.from_disk(meta)` in `loop.py` loads real
`symbol_names`/`pairs` from disk. All three wired together in
`ashlar/api/server.py`.

**Real bug found via the live-model run, fixed:** `qwen2.5-coder:3b` wraps
output in a markdown fence (` ```plinth ... ``` `) despite
`prompts/system.md`'s explicit "no markdown fences" instruction, and
repeats the identical fenced, unparseable output on every one of 4 repair
iterations -- the E001-on-backtick error never points it at the real
problem, so it never converges. This is exactly the "don't trust the
model, constrain it" principle `00_ARCHITECTURE.md` §9 argues for tool
selection, applied to output formatting too. Added
`_strip_markdown_fences()` in `ashlar/harness/loop.py`, applied
immediately after `generate()` and before anything else sees the source.
Confirmed live: the identical task went from `ok=False, max_iterations` to
`ok=True, 2 iterations` after the fix. **Flagging this as the single
highest-value Phase 5 finding so far** -- it's the kind of thing that
would have silently killed the live demo if the model is used unscripted.

**My own authoring bugs found by actually running the real interpreter**
(exactly the point of Pass A-style verification): eval cases 015-017's
embedded broken snippets used `set position at ...`, but `position` is a
bare `position at <lat> <lon>` statement, not a `set`-assignment -- fixed
all three. Eval case 019 originally asked to halt a 20s scenario at 15s,
which is unreachable by design (E070: halt must be at/after scenario
duration) -- reworded to something achievable (15s scenario, halt at
15s). Generated real golden `expected.txt` for eval cases 018-020 (were
TODO placeholders) by actually running solutions through the real
interpreter -- no fabricated traces.

Full suite green: 113 ashlar/eval tests (112 + 1 new fence-stripping
test), 225 language tests, ruff clean, corpus-agnostic invariant holds,
offline check passes.

---
