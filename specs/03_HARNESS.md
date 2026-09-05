# 03 — Harness: the loop, model layer, prompts

**Owner: Emmett.** This is the component that makes the demo work or not work.

The harness is the only process that talks to both the model server and the
MCP server. Ollama never contacts MCP. If you remember one thing, remember
that.

---

## 1. The loop

`ashlar/harness/loop.py`. Normative sequence from `00_ARCHITECTURE.md` §9:

```python
def run_task(prompt: str, corpus: Corpus, emit: Callable) -> TaskResult:
    emit(task_start(prompt))

    # 0. cache
    if hit := memory.cache_lookup(prompt):
        result = mcp.verify(hit.source)
        if result["ok"]:
            emit(cache_hit(hit.key))
            return TaskResult(ok=True, source=hit.source, iterations=0, cached=True)

    # 1-2. DETERMINISTIC pre-fetch — not model-chosen
    keywords = extract_keywords(prompt, corpus.symbol_names)
    hits     = mcp.grep_corpus(build_pattern(keywords), limit=12)
    symbols  = [mcp.lookup_symbol(k) for k in keywords[:6]]
    examples = mcp.get_examples(keywords[0], n=3) if keywords else []

    context = assemble(hits, symbols, examples, memory.top_failures(5))

    # 3-6. generate / verify / repair
    for i in range(1, MAX_ITER + 1):
        source = model.generate(system_prompt(corpus), context, prompt, history)
        emit(model_done(i, source))

        vr = mcp.verify(source)
        emit(verify_result(i, vr))
        if not vr["ok"]:
            history.append(repair_turn(source, vr, mcp))
            emit(repair_start(i + 1, vr["errors"]))
            continue

        # 7. behavioral check against expected output, if a pair exists
        if expected := corpus.expected_for(prompt):
            rr = mcp.verify(source, run=True)
            if rr["stdout"].strip() != expected.strip():
                history.append(diff_turn(source, rr, expected))
                emit(repair_start(i + 1, [{"code": "EDIFF"}]))
                continue

        memory.record_success(prompt, source, i)
        return TaskResult(ok=True, source=source, iterations=i,
                          citations=collect_citations(hits, examples))

    memory.record_failure(prompt, history)
    return TaskResult(ok=False, reason="max_iterations", iterations=MAX_ITER)
```

### Why retrieval is harness-driven, not model-driven

Open-weight models are meaningfully worse at multi-turn tool orchestration
than frontier models. The failure mode is specific and it will happen live:
the model calls `grep_corpus`, receives results, then ignores them or invents
a tool that doesn't exist. Four-iteration repair chains are where it comes
apart.

So the model only **generates and repairs**. Retrieval and verification are
our code. The model may additionally call tools — support that — but the
deterministic pre-fetch always runs first.

This is also the more defensible engineering position, and it plays well to
judges who have watched agent demos stall: we are not hoping the model
behaves, we are constraining it.

### `extract_keywords`

Not fancy. Intersect the prompt's tokens with `symbol_names` from the symbol
table, then add any quoted strings and any tokens matching the language's
identifier pattern. Rank symbol-table matches first. If nothing matches, fall
back to the prompt's rarest three tokens by corpus document frequency.

Test it on all 15 pair tasks. If it misses obviously relevant symbols, fix
this before touching prompts — retrieval quality dominates prompt tuning here.

### `repair_turn` — spend effort here

Repair quality drives your headline number. Include, per error:

- The error line plus three lines of surrounding source, with line numbers
- The full error message (PLINTH messages name the fix — surface that verbatim)
- `lookup_symbol` output for any identifier named in the error
- For `E020`/`E021`/`E022`, `get_examples("bind", 2)` — the gotchas need
  concrete examples, not explanation

Do **not** resend the full conversation history unchanged each iteration.
Resend: system prompt, original context, the current source, and the current
errors. Prior failed attempts should be summarized to one line each
("attempt 1: E041 at line 14"). Local models degrade badly with long
repetitive histories, and context window is scarcer than you think.

## 2. Model layer

`ashlar/harness/model.py`. One class, OpenAI-compatible, nothing else.

```python
from openai import OpenAI

class Model:
    def __init__(self, cfg):
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key or "none")
        self.name = cfg.name
        self.temperature = cfg.temperature

    def generate(self, system, context, prompt, history, tools=None, stream=True):
        ...
```

- Ollama laptop/demo, vLLM for real GPU deployment.
- Cloud endpoint permitted **for development only**. Every eval run records
  which endpoint produced it (`05_EVAL.md`).
- `temperature: 0.1`. Determinism matters more than creativity; also makes
  demo rehearsal meaningful.
- Stream tokens and emit `model_token` events. The frontend needs them and it
  makes the demo feel alive.
- **Model choice is not fixed here.** Benchmark two or three current
  open-weight coding models against `eval/` and record the winner in
  `TASKS.md`. Do not hardcode a model name outside `config.yaml`. Whatever is
  best right now is likely newer than anything named in these specs.

### Timeouts

Local generation on a laptop can take 30s+. Set a generous per-call timeout
(120s) but a hard total task budget (300s) and emit `task_failed` on breach.
Never let the UI hang with no explanation — an unexplained spinner on stage is
worse than a visible failure.

## 3. Prompts

`prompts/system.md`, ~40 lines, loaded and templated by the harness. Not
model config — plain text prepended as the system message.

Content:

```
You write code in {display_name}, a language you have not seen before.
Everything you know about it comes from the provided corpus excerpts and tools.

Rules:
- Never invent a keyword. If you are not certain a symbol exists, call
  lookup_symbol before using it.
- Prefer imitating a real example from the corpus over reasoning from prose
  documentation. Examples reflect the actual grammar; documentation may be
  incomplete or stale.
- The corpus documentation is known to be incomplete. If a construct appears
  in an example but not in the docs, the example is authoritative.
- Every numeric value may require a unit. Check the symbol's dimension.
- Output only source code, no prose, no markdown fences.
- Your output will be compiled. It will be rejected if it does not.

{top_failures_block}
{corpus_conventions_block}
```

`prompts/repair.md` for the repair turn:

```
Your previous attempt failed to compile. Fix only the reported errors.
Do not restructure working code. Do not add features.

Errors:
{errors_with_context}

Reference:
{symbol_lookups}
```

The line about documentation being incomplete and examples being
authoritative is load-bearing — it is what lets the model discover
`inherit from` and `every ... for`, which is the best moment in the demo.
Do not remove it.

## 4. Memory

`ashlar/harness/memory.py`. Writes the tables in `02_BACKEND.md` §2.

```python
cache_lookup(prompt) -> CacheEntry | None    # normalized-text hash + BM25 near-match
record_success(prompt, source, iterations)   # → verified_cache, reindexed
record_failure(prompt, history)              # → failures
top_failures(n) -> list[str]                 # for the system prompt
```

Normalization for cache keys: lowercase, collapse whitespace, strip
punctuation, sort nothing. Exact-hash hit is a fast path; also do a BM25
near-match over cached task texts above a similarity floor and, on a hit,
still run `verify` before returning. **Never return cached source unverified.**

### State this accurately, always

No fine-tuning. No weight updates. Verified snippet cache plus failure memory,
both data-only, both on local disk. When describing the system say exactly
that. Do not say "self-improving" or "learns continuously" without the
qualifier.

The honest version is more persuasive to this audience, because "nothing
leaves the enclave and no weights change" is precisely what makes it
deployable. The constraint is the feature.

## 5. API server for the frontend

`ashlar/api/server.py`. FastAPI, localhost only.

```
POST /task          {"prompt": "...", "corpus": "plinth"} → {"task_id": "t_01"}
GET  /stream/{id}   SSE, emits the §8 event contract
GET  /corpora       → [{"name","display_name","symbols","examples","pairs"}]
POST /corpus/switch {"name": "cobol"} → re-point config, return new manifest
GET  /eval/latest   → last eval report JSON, for the baseline chart
```

Bind `127.0.0.1`. No auth (single-seat, local). CORS allowed for the local
frontend origin only.

`POST /corpus/switch` exists so the demo's closing move — swapping languages
with no code change — is a button rather than a terminal restart.

## 6. Offline verification

Before the event, run the full demo with **wifi off**. Not airplane mode
with a cached page; actually disabled.

Check: no font CDN calls, no npm dev-server fetches, no telemetry from the
OpenAI client library, no embedding model download attempt. Any of these
turns your central claim into a visible lie in front of the audience that
cares most about it.

Add `eval/offline_check.py` that asserts zero outbound connections during a
task run, and put it in the definition of done.

## 7. Definition of done

- [ ] Loop runs end to end against `corpora/stub` before PLINTH exists
- [ ] `MAX_ITER` respected; `task_failed` emitted with last errors
- [ ] Deterministic pre-fetch happens on every task, verified in logs
- [ ] Repair turn includes source context, message, and symbol lookups
- [ ] History is summarized, not accumulated verbatim (assert token count
      does not grow linearly across iterations)
- [ ] Token streaming emits `model_token` events
- [ ] Cache hit path re-verifies before returning
- [ ] `top_failures` injected into system prompt, visible in logged prompt
- [ ] Total task budget enforced; no unexplained hangs
- [ ] SSE stream matches `00_ARCHITECTURE.md` §8 exactly
- [ ] `POST /corpus/switch` works live without restart
- [ ] Full task completes with networking disabled
