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
