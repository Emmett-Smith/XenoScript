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

---
