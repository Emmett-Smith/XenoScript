# LOG

## CURRENT HANDOFF (2026-09-05, ~14:35 local) — READ THIS ONE, supersedes the "MORNING HANDOFF" below

The human is present and interacting live (browser + this session). The
section below ("MORNING HANDOFF") was written when they were asleep and
is now stale in several places (COBOL is built, MUMPS was investigated
and ruled out, several real bugs found and fixed). This section is the
current, accurate state. Full chronological detail is further down the
file, in order.

### What Ashlar is, one paragraph

A coding assistant for languages no model has seen: drop in docs +
examples + a real toolchain, get a verified-output agent for that
language, fully offline. Three corpora exist right now, all real and
switchable live in the UI (header dropdown): **PLINTH** (invented
52-keyword language, proves zero memorization), **COBOL** (real
GnuCOBOL compiler via `brew install gnucobol`, proves real-world
applicability), **stub** (Phase-0 dev scaffolding, harmless, not part
of the demo). A 4th option, **"+ add corpus,"** opens a real form to
onboard any new corpus with an already-installed toolchain — built and
tested tonight, not a mockup.

### How to run it right now

```
ollama serve && curl -s localhost:11434/api/tags   # confirm qwen2.5-coder:3b listed
cd ~/XenoScript && uv sync
uv run python -m ashlar.api.server > /tmp/ashlar_api.log 2>&1 &      # :8000
cd frontend && npm install && npm run dev > /tmp/ashlar_frontend.log 2>&1 &   # :5173
```
Open `http://localhost:5173`. **If you edit any backend Python file**,
you must `pkill -f "ashlar.api.server"` and restart it — it does not
hot-reload, and this bit both the lead agent and a dispatched subagent
tonight (silent stale-code bugs until caught).

### Real, live-verified eval numbers (as of commit `ace0b4e`)

| Corpus | A (cold) | B (docs pasted) | C (tools, no loop) | D (full system) |
|---|---|---|---|---|
| PLINTH | 0% | 5% | 20% | 25% |
| COBOL | 50% | 90% | 20% | 20% |

**These are meant to look different, not the same** — PLINTH's low
numbers prove the model has never seen the language; COBOL's high A/B
prove it's a real language with real training exposure, which is the
whole point of running a second corpus (`05_EVAL.md` §6). Do not average
them or present one "accuracy" figure across corpora. All at `--repeat
1` — `--repeat 3` still not done for either corpus, real run-to-run
variance was observed (values above are trustworthy directionally, not
to the percentage point).

### Every real bug found and fixed this session (chronological, so you can see the pattern: test something live, find it's wrong, fix it, prove the fix)

1. **Markdown-fence stripping** — the live 3B model wrapped output in
   ` ```plinth ` fences despite being told not to, and repeated the
   identical unparseable output for all 4 iterations. Fixed in
   `ashlar/harness/loop.py`'s `strip_markdown_fences`.
2. **3 retrieval bugs** — a contraction ("I've"/"can't") got misread as
   a quote delimiter, producing a garbage 90-char pseudo-keyword;
   `grep_corpus` searched docs before examples, so generic keywords
   exhausted the hit limit before a single example was ever opened;
   one combined grep pattern let a generic keyword's matches crowd out
   a specific one even within the examples tier. Fixed in
   `ashlar/harness/keywords.py` and `ashlar/mcp/server.py`.
3. **The big one: arm C's retrieval had silently drifted from arm D's**
   in `eval/runner.py` (two separate copies of the pre-fetch logic).
   This inflated the apparent "verifier loop contribution" from a real
   5 points to a fake-looking 30. Found by noticing arm C's number
   hadn't moved when arm D's had. Fixed by extracting one shared
   `deterministic_prefetch()` both arms now call. **This is the most
   important process lesson from the whole session**: a suspiciously
   good number is a signal to check the methodology, not a result to
   report.
4. **Hyphenated-identifier tokenization** — found via real COBOL:
   `WS-INDEX` was splitting into two spurious symbols ("WS", "INDEX")
   because the tokenizer was only built for PLINTH's underscore
   convention. Fixed in `ashlar/ingest/indexer.py` /
   `ashlar/ingest/symbols.py`.
5. **Generic text-output verifier adapter** — GnuCOBOL has no `--json`
   mode, prints plain `file:line: severity: message` to stderr.
   `ashlar/mcp/sandbox.py` only understood JSON-emitting toolchains
   until this session. Added `verifier.output_format`/`error_regex` to
   the `meta.yaml` contract, corpus-agnostic (the regex lives in the
   corpus's own `meta.yaml`, never in `ashlar/` code).
6. **Terminal/output panel showed a real compiler warning as if it were
   a failure** — stderr was always styled `--fault` (red) regardless of
   whether the run actually succeeded. Fixed: red only when `ok` is
   false, dim/gray otherwise.
7. **Cross-corpus eval-report mislabeling — two compounding bugs.**
   `build_report()` recorded `config.yaml`'s static default corpus, not
   the corpus actually passed via `--corpus`; separately, `GET
   /eval/latest` returned the single newest report file with zero
   awareness of which corpus was active in the UI. Together: running a
   COBOL sweep made the **PLINTH** baseline chart briefly show COBOL's
   (much higher) numbers, live, on screen. Fixed both ends: the report
   now always carries the real corpus it tested; `GET
   /eval/latest?corpus=X` filters by it; the frontend passes the active
   corpus and double-checks the response. **General lesson: any report
   artifact needs its own identity checked at read time, "latest" is
   almost never the right query once more than one axis can vary.**
8. **`eval/runner.py`'s report was only written once, at the very end**
   — a multi-arm sweep that gets killed partway through used to lose
   *everything*, including already-completed arms. Now writes/
   overwrites incrementally after each arm.

### Two feature requests just implemented (both live-verified, both need a decision or FYI)

- **97% output-similarity scoring, replacing exact match** — per direct
  request: "run until it produces output, then score how close that
  output is to the source of truth, ≥97%." Implemented in
  `ashlar/harness/loop.py` (`output_similarity`, stdlib `difflib`,
  shared with `eval/runner.py`'s grading). An empty/failed run is never
  accepted regardless of what the ratio math would say. **This changed
  a normative contract line in `00_ARCHITECTURE.md` §9 step 7** (was
  exact match) — updated the doc to match, since that's a change that
  needs explicit human sign-off and this request constitutes it.
- **Synonym/stem resolution for "not found" symbol lookups** — a prompt
  using "outputting" against PLINTH now also resolves to the real
  symbol "report" (PLINTH's actual output-ish keyword), instead of a
  flat "not found." Fixed vocabulary clusters (output/print/display/...,
  loop/repeat/..., etc.) in `ashlar/harness/keywords.py`, corpus-
  agnostic — confirmed a cluster with no real-symbol member resolves to
  nothing, never fabricates a symbol.

### MUMPS — investigated, ruled out for this machine, with real evidence

User asked about adding MUMPS (healthcare-industry angle) as a 3rd
corpus. Checked: no Homebrew formula, no Docker, and decisively —
YottaDB/GT.M's own `CMakeLists.txt` only implements `Linux` and `AIX`
platform branches; there's no `sr_darwin` directory in the source tree
at all (unlike `sr_linux`, which holds the OS-specific process/signal/
shared-memory code the runtime needs). Cloned the real repo and
confirmed `cmake ..` fails immediately with an explicit `FATAL_ERROR` on
unsupported OS. **Not "hard," architecturally Linux/AIX-only.** Real
path forward: a Linux VM — prebuilt packages exist there, trivial.
Not pursued further; tell the human if a Linux box/VM becomes available.

### What's NOT done — say this plainly if asked

- `--repeat 3` on any arm, either corpus (real variance observed, e.g.
  arm B swung 5%→0% with zero code change — single runs aren't solid).
- Model bake-off (`TASKS.md` P1) — only `qwen2.5-coder:3b` was ever
  available on this machine tonight.
- Physical projector legibility check (none available).
- Literal wifi-off reload (code + `eval/offline_check.py` both say
  clean; not physically tested with the radio off).
- Composition-category PLINTH tasks (0/3 in eval) — **root cause now
  confirmed live, post-handoff**: re-ran the exact "identical error
  every iteration" signature by hand (`POST /task` with
  `{"corpus":"plinth","prompt":"write a program outputting the message
  hello"}`). The repair turn already surfaced `report`'s real
  `valid_parents=[execute]` via `lookup_symbol`, correctly, every
  iteration — but nothing in `prompts/repair.md` told the model what a
  `valid_parents` entry *means to do*, so `qwen2.5-coder:3b` regenerated
  byte-identical wrong source 4 times in a row. Added a generic
  ("nest inside one of these blocks, don't repeat the top-level line")
  instruction line to `prompts/repair.md`, corpus-agnostic, 155 tests
  still pass (commit `ba4285e`). Re-ran the identical prompt afterward:
  this 3B model is also plainly stochastic — the retry produced a
  *different* wrong candidate (bare `hello`, no `report` at all) that
  never triggered the new instruction in the first place, so the fix's
  real effect on this specific prompt is unconfirmed. **Conclusion: this
  is a real, now partially-mitigated repair-prompt gap, but convergence
  on hard prompts is still fundamentally capped by this one small
  local model's weak instruction-following — not a retrieval or
  backend logic bug.** Don't chase this further by tuning prompts
  against one cherry-picked example; if it matters, the real fix is a
  stronger model (bake-off, still blocked on availability).
- `--repeat 3`'s absence means every percentage above should be read as
  "roughly this," not "exactly this."

### User's stated priority, most recent message

**"Primarily most concerned with backend returning correct results as
we'll likely migrate over to a fancy ui."** — the current frontend may
be replaced. Bias further effort toward `ashlar/`, `languages/`,
`corpora/`, `eval/` correctness over frontend polish. Keep testing live
prompts against real corpora, comparing actual vs. expected output,
and fixing whatever's actually wrong — that's the standing instruction
("keep running examples, compare output, keep iterating until the
results are working properly"), not a one-time task.

### Immediate next steps, in priority order

1. Keep running varied real prompts against both PLINTH and COBOL,
   watching for anything that looks wrong (retrieval misses, repair
   loops that thrash, wrong-looking output) — this is an open-ended,
   standing instruction, not a checklist to finish.
2. `--repeat 3` sweeps once there's a quiet stretch (30-90 min each,
   background-able) — needed before any number here is quote-safe.
3. If a Linux VM/box ever becomes available: MUMPS via YottaDB's
   prebuilt packages (trivial there, blocked here).
4. Trace a composition-category PLINTH failure the way the "inherit
   from" case was traced earlier, to find its real root cause.

---

## MORNING HANDOFF (2026-09-05, ~05:20 local)

**State:** the full pipeline works end to end for real — invented
language, real interpreter, real MCP tools, real repair loop, real UI —
against the live model that appeared mid-session. Eval numbers are
honest but small-sample; need `--repeat 3` before quoting anywhere.

**NEEDS HUMAN:** (1) `ORCHESTRATOR.md` says dir `xenoscript/`; `00_ARCHITECTURE.md`/`README.md` say `ashlar/`. Went with `ashlar/` — say if wrong. (2) Model bake-off never ran, only `qwen2.5-coder:3b` was ever available.

**Run it:**
```
ollama serve && ollama list                       # confirm qwen2.5-coder:3b
cd ~/XenoScript && uv sync
uv run python -m ashlar.ingest --corpus corpora/plinth
uv run python -m ashlar.api.server                # :8000
cd frontend && npm install && npm run dev          # :5173, open it
```
Try: "give a platform an altitude of fifteen hundred meters written the
way PLINTH expects" — real E043 fail→repair→pass. Corpus switch dropdown
→ `stub` and back, confirmed live twice, no restart.

**Unverified:** physical projector (none available); literal wifi-off
reload (code + `eval/offline_check.py` both say clean, not physically
tested); `--repeat 3` on any arm; COBOL corpus (not built, P1).

**Eval — read `eval/FAILURE_ANALYSIS.md`'s top section first, it
corrects itself.** `--repeat 1`, same commit: A=0%, B=0-5% (varied on
*unchanged* code), C=20%, D=25%. D−C=5pp, **not** the 30pp an earlier
buggy comparison showed (arm C's retrieval had drifted from arm D's —
found and fixed). Before quoting any number:
`uv run python -m eval.runner --all-arms --corpus plinth --repeat 3`
(~60-90 min, writes incrementally, safe to background).

**Pass B, done vs. remaining:** done — fence-stripping (was blocking
every live task), 3 retrieval bugs, arm-C/D dedup. Remaining — repair
context should re-check *all* required fields, not just the one named
in the error (E020/E052 pattern); widen `get_examples` past comments to
real code; composition tasks (0/3) un-root-caused.

**Next, in order:** (1) `--repeat 3` above, everything rests on it;
(2) COBOL corpus — strongest rebuttal to "you wrote both ends," nothing
blocks it; (3) trace a composition failure like case 009 was traced.

**Invariants:** [x] no unverified source reaches the user · [x] no
language logic under `ashlar/` (asserted in `check.sh`) · [x] full task
runs with networking disabled (`offline_check.py`; not physically
re-tested) · [x] corpus swap via config change alone, and live via
`POST /corpus/switch`, twice in a row.

Full detail below, in build order.

---

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

### Phase 4 — eval runner built, real numbers coming in

`eval/runner.py`: arms A/B/C as single-shot generate+grade, D/E via the
real `run_task` loop. Grading applies each case's `rubric.yaml` exactly
(must_contain/must_not_contain, then real `verify()`/`verify(run=True)`).
Self-tested against `FakeModel` first (`eval/test_runner.py`, zero
network) — category distribution assertion (4/4/3/3/3/3=20), all runnable
arms exercised, arm E's missing-credentials guard fails loudly. All green.

**Real numbers, live `qwen2.5-coder:3b`, `--repeat 1` (time-boxed — see
below), git `25c1ff5`:**

| Arm | verified-correct | p50 | p95 |
|---|---|---|---|
| A (cold) | **0%** (0/20) | 5.5s | 10.6s |
| B (docs pasted) | 5% (1/20) | 32.5s | 90.5s |
| C (tools, no loop) | 5% (1/20) | 11.5s | 20.3s |
| D (full system) | *running* | | |

Arm A landing at exactly 0% is the number the whole pitch rests on
(05_EVAL.md #1) and it's real, not asserted. B being slow (repeat-1 alone
took 12m15s for 20 tasks) confirms the spec's prediction that long-context
docs-pasting is a weak, slow competitor on a 3B local model. Arm D
(the product) is running now — full report + failure analysis in Phase 5.

**Time-boxing note, stated honestly:** `05_EVAL.md` §4 asks for
`--repeat 3` on arms C/D/E. At B's observed pace (~37s/task average),
3 full repeats across C/D/E would run into the hour(s) range on this 3B
CPU/local-GPU model. Running `--repeat 1` first to get real numbers landed
in this session, then revisiting `--repeat 3` in Phase 5 if time allows;
if it doesn't, the exact commands are in the morning handoff. This is a
real constraint, not corner-cutting on the metric itself — every number
reported is real, single-run numbers are just single-run, honestly labeled.

### Phase 3 — frontend agent: done, merged

Worktree `/Users/owner/XenoScript/.claude/worktrees/agent-a7fcda841d82d3e47`
branch `worktree-agent-a7fcda841d82d3e47`. Merged clean into master
(no conflicts — new `frontend/` tree only). `npm run build` re-verified
from master post-merge: succeeds, 545ms, `dist/` produced.

Vite+React+TS, all 3 panels, verdict block + attempt ledger, built and
**actually exercised in a real browser** (the agent used the Chrome
automation tool, not just code review) against all 3 recorded fixtures
plus the real running API server end-to-end (real `EventSource`, real
`POST /corpus/switch`, real Ollama answering). Found and fixed 2 real
rendering bugs this way (verdict text overflow, ledger column too
narrow) — exactly the value of actually running a UI instead of trusting
it compiles.

**Fonts:** real IBM Plex Sans/Mono woff2 files, vendored locally under
`frontend/public/fonts/`. Fetched once from unpkg during the build
session to obtain the actual files (this machine has outbound network
access) — the shipped app's CSS references only local `/fonts/...` paths,
never a CDN URL at runtime, so this doesn't violate the offline-at-runtime
invariant. Noting this plainly since "no CDN asset" is a hard rule and I
want the distinction (build-time fetch vs. runtime reference) on record.

**Fixture replay:** real recorded JSONL (byte-identical to
`eval/fixtures/event_streams/`, copied into `frontend/public/fixtures/`)
replayed on a fixed per-event-type delay for watchability — event
*content* untouched, gated behind `?fixtures=1` + `import.meta.env.DEV`,
never present in a production build. The real `fetch`/`EventSource` path
against `localhost:8000` is the only path in a shipped build.

**Honest gaps:** not tested on a physical projector (none available).
`npm run dev` with networking physically disabled wasn't separately
re-verified (no CDN reference exists in the code, so this is very likely
fine, but "very likely" isn't "verified" — worth 30 seconds in Phase 5).

**Ambiguities resolved, adopting as-is:** event→verdict-state mapping
(documented inline in `useTaskStream.ts`); `MAX_ITER=4` hardcoded as a UI
display default (matches the documented architecture constant, not
fabricated, since no endpoint exposes it); one internal-only `__reset`
reducer action for corpus-switch panel clearing (not part of the §8 union).

One process note: shipped as a single commit rather than incremental
commits (flagged by the agent itself). Not going to unpick that
retroactively — the code is what matters and it's real, tested work.

---

### Phase 5 — the critical correction: arm C had a retrieval-drift bug

After fixing 3 real retrieval bugs found via live-model diagnosis
(contraction-quote parsing, docs-before-examples ordering, one shared
grep limit letting a generic keyword crowd out a specific one — see the
`Phase 5 Pass B` commits), a before/after eval comparison showed a
striking **30-point D-minus-C gap** (D=35%, C=5%) — exactly the headline
number `05_EVAL.md` #1 wants ("D minus C is the verifier's
contribution... your headline claim"). **It was wrong.** `eval/runner.py`
's arm C had its own separate copy of the deterministic pre-fetch logic.
When the retrieval fixes landed in `ashlar/harness/loop.py` (used by
`run_task`, i.e. arm D), arm C's copy silently did not get them — the two
arms were no longer measuring the same retrieval quality, so part of
that "gap" was a code-drift bug, not the verifier loop's effect.

Caught by noticing arm C's number hadn't moved in a before/after
comparison when arm D's had. Fixed by extracting one shared
`deterministic_prefetch()` (+ `PrefetchResult`, `_NullEmitter`) in
`ashlar/harness/loop.py`; both `run_task` and eval's arm C now call it.

**Corrected, apples-to-apples numbers** (same commit `c4dbb6c`, same
corpus, `--repeat 1`, run within about an hour of each other):

| Arm | Verified-correct |
|---|---|
| A (cold) | 0% (0/20) |
| B (docs pasted) | 0% (0/20) — an *earlier* run of the same, unchanged B logic scored 5% (1/20); pure run-to-run model variance |
| C (tools, no loop) | 20% (4/20) |
| D (full system) | 25% (5/20) |

**D minus C = 5 percentage points**, not 30. That's the honest number.
Given B's 5%→0% swing on literally unchanged logic, n=20/repeat=1 is not
solid ground for a pitch claim either way — `--repeat 3` is genuinely
needed before quoting this publicly, not just a spec formality. Full
writeup, including the corrected top-of-document framing, in
`eval/FAILURE_ANALYSIS.md`.

**This is the single most important process lesson from tonight's
build:** the impressive number was wrong, and catching that before it
reaches a pitch deck is exactly the point of Phase 5's "verify, then
improve" ordering — a suspiciously good number is itself a signal to
check the methodology, not a result to report.

Also fixed while producing these numbers: the eval runner now writes its
report incrementally after each arm. A `--all-arms --repeat 3` run got
killed mid-flight this session and lost everything — including 3
already-completed arms' results — because the report previously only
wrote once at the very end.

Ranked improvement list, actually executed this session (Phase 5 Pass B,
ranked by demo impact per hour, per `ORCHESTRATOR.md` §3's bias list):

1. **Error message quality (ORCHESTRATOR's #1 priority)** — already
   strong from the language agent's work (E022/E043 name the fix
   verbatim); confirmed via the failure analysis that repair converges
   reliably exactly when the message names a fix, and stalls when it
   can't (an invented keyword like `copy`/`as` has no fix to name). No
   further change needed here; the finding validates the existing design.
2. **`extract_keywords` accuracy (#2 priority)** — fixed for real: the
   contraction-quote bug affects any prompt phrased with contractions,
   which is realistic natural-language phrasing, not an edge case.
3. **Markdown-fence stripping** — not on the original ranked list, but
   found live and fixed first because it was completely blocking every
   single live-model task before the fix (0% pass rate on trivial tasks).
   Judgment call: a demo-blocking bug outranks the pre-written list.
4. **Repair-turn context assembly (#3 priority)** — partially addressed:
   the fair-share grep fix and non-block-kind `get_examples` anchor both
   improve what context repair turns see. The E020/E052 "fixes one thing,
   doesn't check for another" pattern (§3 of the failure analysis) is a
   further, un-implemented version of this — flagged as recommended next
   step #3, not done tonight (time).
5. **BM25 underscore tokenization (#4 priority)** — backend already
   tested and confirmed this in Phase 1 (`\w+` naturally keeps
   `noise_floor` as one token); nothing to fix.
6. **Verdict block and attempt ledger fidelity (#5 priority)** — the
   frontend agent's own browser-verified testing (Phase 3) already
   confirms this against real fixtures; two real rendering bugs found and
   fixed there (text overflow, ledger column width).

Not done, time-boxed, honest: TASKS.md's remaining P1 items (COBOL
corpus, warm-vs-cold cache comparison, model bake-off, corpus-switcher
UI polish beyond what's built). Exact next commands for all of this are
in the morning handoff below.

---

### Session continues, live — human present, requested ongoing iteration

Human came back to interact with the running demo directly (browser
automation, live prompts). Notable findings from that interaction:

- **MUMPS investigated and ruled out for tonight, with real evidence.**
  Human asked about adding MUMPS (healthcare-industry angle) as a third
  corpus, same pattern as COBOL. Checked: no Homebrew formula for
  GT.M/YottaDB, no Docker on this machine, and critically — YottaDB's own
  `CMakeLists.txt` only implements `Linux` and `AIX` platform branches;
  there's no `sr_darwin` directory in the source tree at all (unlike
  `sr_linux`, which holds the OS-specific process/signal/shared-memory
  code the M runtime needs). Cloned the real repo and confirmed the build
  fails immediately at `cmake ..` with an explicit `FATAL_ERROR` on
  unsupported OS. This isn't "untested on Mac," it's architecturally
  Linux/AIX-only. Real path forward: a Linux VM (trivial there, prebuilt
  packages exist) — noted for the human, not pursued further tonight.
- User asked to leave the machine running (caffeinate) and keep iterating
  autonomously. Dispatched a background agent for 3 live-reported issues
  (COBOL warning rendering as a fault-red error despite `ok: true`; stale
  25% baseline; wanting to see a real multi-cycle repair before verified)
  while continuing other work directly.
- **Real coordination lesson**: dispatched agent and lead agent both tried
  to drive the same Chrome tab concurrently and stepped on each other
  (a modal got closed mid-interaction). Backed off browser/live-model work
  entirely while the agent had it, switched to pure code review / corpus
  content / non-model-calling work until it finished. Worth remembering:
  browser automation and live-model calls are exclusive resources when a
  background agent is using them too, same as any shared external system.

**Agent's 3 fixes, all landed:**
1. `TerminalPanel`'s stderr was always styled `--fault` regardless of
   `runOutput.ok` — a benign GnuCOBOL warning on a real `ok: true` success
   looked identical to a failure. Fixed: `--fault` only when `ok` is
   false, `--dim` otherwise. Confirmed live.
2. Fresh `--all-arms --repeat 1` sweep on current code: **A=0%, B=5%,
   C=20%, D=25%** — same as the last corrected numbers, now with clean
   current-commit provenance. Baseline chart confirmed reading it live.
3. Found a real (if not 100%-reproducible) multi-cycle repair prompt: a
   deliberately broken snippet combining the spacing gotcha (E043) *and*
   the set-vs-bind gotcha (E022) in one source, which converges through
   both distinct errors before verifying on attempt 2-3. Documented
   honestly that model sampling variance means this doesn't show two
   distinct errors on every single run — sometimes the model gets one of
   the two right on the first try. Also documented several rejected
   attempts (oscillating failures that never converge) rather than
   pretending only the good result was tried.

**My own work while the agent had the browser/model:**
- Reviewed `/corpus/create` and `AddCorpusModal.tsx` line by line — no
  bugs found, solid work.
- COBOL corpus: 3 more real pairs (PERFORM UNTIL, named paragraphs,
  SUBTRACT), now 9 pairs, every one compiled+run through real `cobc`.
- Built per-corpus eval case set support (`cases_dir_for`) — additive,
  PLINTH's flat 20 cases never moved, zero risk to the in-flight sweep
  (confirmed `load_cases()` runs once before the arms loop, so editing
  the module on disk mid-run is safe; Python doesn't hot-reload).
- **Caught a real bug in my own change before committing it**: the flat
  fallback iteration treated the new `eval/cases/cobol/` container
  directory as if it were itself a case, crashing on a missing
  `rubric.yaml`. Fixed by skipping any subdirectory without one.
- 10 real COBOL eval cases: basic structure, arithmetic (`COMPUTE`,
  `ADD ... GIVING`, `SUBTRACT`), a genuine COBOL gotcha (`MOVE`-ing a
  7-character literal into `PIC X(3)` truncates silently to `"TOO"`, no
  compile error — confirmed live), conditionals, both loop shapes, one
  repair task. Every expected output captured from real `cobc` execution,
  every case re-verified against its own solution via the runner's own
  `_grade()` afterward.

COBOL eval sweep (`--all-arms --corpus cobol --repeat 1`) running now —
the real "you wrote both ends" rebuttal number, in progress.

### COBOL eval sweep done — and it surfaced a real, serious bug on the way

**Numbers, real, `--repeat 1`:** A=50%, B=90%, C=20%, D=20%.

**This is a genuinely different shape than PLINTH's (A=0%, B=5%, C=20%,
D=25%), and that's the whole point, not a problem.** PLINTH exists to
prove zero memorization — A near 0% is the load-bearing number.
COBOL exists to prove real-world applicability with a compiler nobody
here wrote — and COBOL being real, decades-old, and heavily represented
in training data means the model plausibly already "knows" some COBOL,
so A=50% and B=90% (paste the docs, no tools) are *expected*, not
embarrassing. `05_EVAL.md` §6 says this outright: "note honestly that
COBOL arm A will not be near zero... the two corpora measure different
things." B beating D here (90% vs 20%) is a real, interesting, honest
finding worth its own line in the pitch: for a language the model
already knows syntax for, more context (the full manual) helps more
than narrow deterministic retrieval + a repair loop — the verifier
loop's value is highest precisely when the model *doesn't* already know
the syntax, which is PLINTH's story, not COBOL's. Do not average these
two numbers together or present one "verified-correct rate" as if it
meant the same thing across corpora.

**The bug, found by watching the live UI mid-sweep:** while this sweep
was running, `localhost:5173`'s Baseline chart — still showing PLINTH —
displayed **50%**, not the real PLINTH number (25% at the time). Two
independent bugs compounded:

1. `eval/runner.py`'s `build_report()` recorded `cfg.corpus`
   (`config.yaml`'s static default, `"plinth"`) instead of the corpus
   actually passed via `--corpus`. Every report ever written with a
   `--corpus` override this session was silently mislabeled — including,
   it turns out, some of tonight's earlier PLINTH-vs-arm-C corrections,
   though those happened to be correct by coincidence since the config
   default *was* "plinth" at the time.
2. `GET /eval/latest` returns the single newest file overall, with zero
   awareness of which corpus is active in the UI. There was no way for
   either side to detect a mismatch.

**Fixed both, properly:** `build_report()` now takes `corpus_name`
explicitly. `GET /eval/latest?corpus=<name>` filters reports by their
own `corpus` field and returns the newest one *for that corpus*, falling
back to the old "just the newest file" behavior with no param. The
frontend passes the active corpus and keeps a defensive check on the
response too (belt and suspenders — the fix must hold even if a caller
forgets the query param). Also corrected the one report already written
with the wrong label (`corpus: plinth` → `cobol`, on a file whose actual
test data — A=50/B=90/C=20/D=20 — was always correct, only the label was
wrong; verified this was a safe correction of known ground truth, not a
number pulled from nowhere). Confirmed live in the browser, both
corpora, each showing its own correct numbers with zero cross-talk.

Real lesson for this kind of multi-corpus system generally: **any report
artifact needs its own identity carried inside it, checked at read time,
not inferred from "whichever one happens to be newest."** "Latest" is
almost never actually the right query once there's more than one axis
(here: corpus) a report can vary along.

---
