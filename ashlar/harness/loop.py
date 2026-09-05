"""The loop: generate -> verify -> repair. `run_task` implements
00_ARCHITECTURE.md #9 / 03_HARNESS.md #1 exactly.

Deviations from the pseudocode, and why (all in the report, repeated here so
the code is self-documenting):

- `run_task` takes an explicit `deps: HarnessDeps` bundling `model`,
  `tool_client`, `memory`, `max_iter`, `task_budget_s` instead of reading
  module-level globals. The pseudocode's `mcp.*` and `memory.*` calls read as
  globals; making them injected dependencies is what makes this function
  testable against `FakeModel`/`FakeToolClient` with zero network access.
- `history` is a `list[HistoryTurn]` (repair.py), not raw strings. Only the
  most recent turn's full detail is sent to the model each iteration; every
  earlier turn collapses to a one-line summary. See `repair.render_history`.
- Step 7 (behavioral check against an expected pair) does not emit its own
  `verify_start`/`verify_result` pair in the event stream -- the contract in
  00_ARCHITECTURE.md #8 doesn't show a distinct event for it, and the
  fail-then-succeed acceptance test in 03_HARNESS.md's brief only exercises
  compile-only tasks. The `verify(source, run=True)` call itself still
  happens deterministically per the pseudocode.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ashlar.config import CorpusMeta
from ashlar.harness.events import EventEmitter
from ashlar.harness.keywords import extract_keywords
from ashlar.harness.memory import Memory, normalize_task
from ashlar.harness.model import ModelClient
from ashlar.harness.prompts import system_prompt
from ashlar.harness.repair import HistoryTurn, diff_turn, render_history, repair_turn
from ashlar.harness.tool_client import ToolClient

MAX_CONTEXT_CHARS = 4000  # cheap proxy for the ~4k-token budget; no local
                          # tokenizer is guaranteed available offline.
PREFETCH_GREP_LIMIT = 12
PREFETCH_SYMBOL_LIMIT = 6
PREFETCH_EXAMPLE_N = 3


@dataclass
class Corpus:
    """The harness's minimal view of a corpus. `symbol_names` and `pairs`
    are the Phase-2 integration points: real values come from the backend's
    symbol table (`ashlar/ingest/symbols.py`) and `corpora/<name>/pairs/`
    respectively, neither of which exists in this worktree tonight. Wiring
    them in later is passing different data into this constructor -- no
    change to `run_task`'s body.
    """

    meta: CorpusMeta
    symbol_names: list[str] = field(default_factory=list)
    pairs: dict[str, str] = field(default_factory=dict)  # normalized task text -> expected stdout

    @property
    def display_name(self) -> str:
        return self.meta.display_name

    def expected_for(self, prompt: str) -> str | None:
        return self.pairs.get(normalize_task(prompt))

    @classmethod
    def from_disk(cls, meta: CorpusMeta) -> Corpus:
        """Loads `symbol_names` from `<corpus>/.index/symbols.db` (if the
        backend's ingest has run for this corpus) and `pairs` from
        `<corpus>/pairs/*/{task.txt,expected.txt}`. Corpus-agnostic: reads a
        fixed schema and a fixed directory layout, no per-language
        branching. Missing pieces (no ingest yet, no pairs/) degrade to
        empty rather than raising -- retrieval/behavioral-check just has
        less to work with, honestly."""
        symbol_names: list[str] = []
        db_path = meta.root / ".index" / "symbols.db"
        if db_path.exists():
            import sqlite3

            conn = sqlite3.connect(db_path)
            try:
                symbol_names = [row[0] for row in conn.execute("SELECT name FROM symbols")]
            finally:
                conn.close()

        pairs: dict[str, str] = {}
        pairs_dir = meta.root / "pairs"
        if pairs_dir.is_dir():
            for d in sorted(pairs_dir.iterdir()):
                task_file, expected_file = d / "task.txt", d / "expected.txt"
                if task_file.exists() and expected_file.exists():
                    pairs[normalize_task(task_file.read_text())] = expected_file.read_text()

        return cls(meta=meta, symbol_names=symbol_names, pairs=pairs)


@dataclass
class HarnessDeps:
    model: ModelClient
    tool_client: ToolClient
    memory: Memory
    max_iter: int = 4
    task_budget_s: int = 300
    top_failures_n: int = 5


@dataclass
class TaskResult:
    ok: bool
    source: str | None = None
    iterations: int = 0
    cached: bool = False
    citations: list[Any] = field(default_factory=list)
    reason: str | None = None
    last_errors: list[Any] = field(default_factory=list)


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _render_top_failures(top_failures: list[str]) -> str:
    if not top_failures:
        return ""
    lines = ["Common failure patterns for this language (fix these proactively):"]
    lines.extend(f"- {f}" for f in top_failures)
    return "\n".join(lines)


def assemble(
    hits: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    examples: list[dict[str, Any]],
    top_failures: list[str],
) -> str:
    """Builds the retrieval context block handed to the model as `context`.
    Deterministic, harness-owned -- this is steps 2-3 of the loop, not
    anything the model asked for."""
    parts: list[str] = []

    clean_hits = [h for h in hits if "error" not in h]
    if clean_hits:
        parts.append("Relevant corpus excerpts:")
        for h in clean_hits[:8]:
            ctx_lines = list(h.get("context_before", [])) + [h.get("text", "")] + list(h.get("context_after", []))
            parts.append(f"  {h.get('file')}:{h.get('line')}\n{_indent(chr(10).join(ctx_lines))}")

    found_symbols = [s for s in symbols if s.get("found")]
    if found_symbols:
        parts.append("Known symbols:")
        for s in found_symbols:
            parts.append(
                f"  {s.get('name')}: kind={s.get('kind')} arg_shape={s.get('arg_shape')} "
                f"dimension={s.get('dimension')} valid_parents={s.get('valid_parents')}"
            )

    clean_examples = [e for e in examples if "error" not in e]
    if clean_examples:
        parts.append("Verified examples:")
        for ex in clean_examples[:PREFETCH_EXAMPLE_N]:
            parts.append(f"  {ex.get('file')}:{ex.get('start')}-{ex.get('end')}\n{_indent(ex.get('text', ''))}")

    if top_failures:
        parts.append(_render_top_failures(top_failures))

    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


def collect_citations(hits: list[dict[str, Any]], examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for h in hits:
        if "file" in h:
            citations.append({"file": h["file"], "line": h.get("line")})
    for ex in examples:
        if "file" in ex:
            citations.append({"file": ex["file"], "start": ex.get("start"), "end": ex.get("end")})
    return citations


def _elapsed(start: float) -> float:
    return time.monotonic() - start


_FENCE_RE = re.compile(r"^\s*```[^\n]*\n(.*?)\n?```\s*$", re.DOTALL)


def strip_markdown_fences(source: str) -> str:
    """Local models routinely wrap output in a markdown code fence despite
    `prompts/system.md`'s explicit "output only source code, no markdown
    fences" instruction -- observed live in Phase 2 integration against
    qwen2.5-coder:3b, which fenced identical output on every one of 4
    repair iterations and never once produced anything that could parse
    (every attempt failed with the same E001 on the fence's backtick).
    00_ARCHITECTURE.md #9's whole premise is that the harness constrains
    the model rather than trusting it to follow instructions -- this is
    that principle applied to output formatting, not just tool selection.
    Strips one leading/trailing fence (with or without a language tag on
    the opening line) if the entire source is wrapped in one; otherwise
    returns it unchanged."""
    m = _FENCE_RE.match(source)
    return m.group(1) if m else source


class _NullEmitter:
    """No-op stand-in for EventEmitter, for callers (the eval runner's
    single-shot arm C) that want the pre-fetch's retrieval behavior but
    have no event stream to write to."""

    def tool_call(self, *args: Any, **kwargs: Any) -> None:
        pass

    def tool_result(self, *args: Any, **kwargs: Any) -> None:
        pass


@dataclass
class PrefetchResult:
    keywords: list[str]
    hits: list[dict[str, Any]] = field(default_factory=list)
    symbols: list[dict[str, Any]] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    example_symbol: str | None = None


def deterministic_prefetch(
    prompt: str,
    symbol_names: list[str],
    tool_client: ToolClient,
    emitter: Any = None,
) -> PrefetchResult:
    """Steps 1-2 of 00_ARCHITECTURE.md #9's loop: harness-driven, not
    model-chosen. Shared by `run_task` (arm D/E) and the eval runner's
    arm C (`eval/runner.py`) so that comparison is a true isolation of
    the verifier loop's contribution -- both need identical retrieval
    quality, or "D minus C" measures retrieval drift too, not just the
    loop's effect (05_EVAL.md #1's whole point for that arm).

    `emitter` may be any object with `.tool_call(name, args)` and
    `.tool_result(name, count, preview)` methods (typically an
    `EventEmitter`); pass `None` when there's no event stream to write to.
    """
    if emitter is None:
        emitter = _NullEmitter()

    keywords = extract_keywords(prompt, symbol_names)

    # One grep_corpus call per keyword, each capped to a fair share of the
    # total budget, rather than one combined alternation with one shared
    # limit. Phase 2 live-model diagnosis: extract_keywords legitimately
    # ranks symbol-table matches first (03_HARNESS.md #1's own algorithm),
    # but structural keywords ("define", "platform") are symbols too and
    # appear in nearly every file -- a combined pattern let them exhaust
    # the limit on the very first file(s) touched, before a rarer,
    # genuinely diagnostic keyword (a specific identifier name) ever got a
    # single hit. This does not change what grep_corpus does (still a dumb
    # regex primitive, 00_ARCHITECTURE.md #7) -- it changes how the
    # harness *calls* it, which is exactly the kind of tuning §1 assigns
    # to this file, not to the MCP server.
    hits: list[dict[str, Any]] = []
    if keywords:
        per_kw_limit = max(1, PREFETCH_GREP_LIMIT // len(keywords))
        seen_hit_keys: set[tuple[Any, Any]] = set()
        for kw in keywords:
            if len(hits) >= PREFETCH_GREP_LIMIT:
                break
            emitter.tool_call("grep_corpus", {"pattern": kw, "limit": per_kw_limit})
            kw_hits = tool_client.grep_corpus(re.escape(kw), limit=per_kw_limit)
            clean = [h for h in kw_hits if "error" not in h]
            emitter.tool_result("grep_corpus", len(clean), clean[:5])
            for h in clean:
                key = (h.get("file"), h.get("line"))
                if key not in seen_hit_keys:
                    seen_hit_keys.add(key)
                    hits.append(h)

    symbols: list[dict[str, Any]] = []
    for k in keywords[:PREFETCH_SYMBOL_LIMIT]:
        emitter.tool_call("lookup_symbol", {"name": k})
        res = tool_client.lookup_symbol(k)
        emitter.tool_result("lookup_symbol", 1 if res.get("found") else 0, [res])
        symbols.append(res)

    # Prefer a non-structural keyword (attribute/statement, not a bare
    # block opener like "define"/"platform") as the anchor for
    # get_examples -- a block keyword appears in every example file
    # equally, so it carries no discriminative signal about *which*
    # example is relevant to this specific prompt.
    example_symbol = keywords[0] if keywords else None
    for k, res in zip(keywords[:PREFETCH_SYMBOL_LIMIT], symbols):
        if res.get("found") and res.get("kind") not in ("block", None):
            example_symbol = k
            break

    examples: list[dict[str, Any]] = []
    if example_symbol:
        emitter.tool_call("get_examples", {"symbol": example_symbol, "n": PREFETCH_EXAMPLE_N})
        examples = tool_client.get_examples(example_symbol, n=PREFETCH_EXAMPLE_N)
        emitter.tool_result("get_examples", len(examples), examples[:PREFETCH_EXAMPLE_N])

    return PrefetchResult(
        keywords=keywords, hits=hits, symbols=symbols, examples=examples, example_symbol=example_symbol
    )


def run_task(
    prompt: str,
    corpus: Corpus,
    emit: Callable[[dict[str, Any]], None],
    deps: HarnessDeps,
    task_id: str | None = None,
) -> TaskResult:
    task_id = task_id or f"t_{uuid.uuid4().hex[:8]}"
    emitter = EventEmitter(task_id, emit)
    start = time.monotonic()
    emitter.task_start(prompt)

    def budget_exceeded() -> bool:
        return _elapsed(start) > deps.task_budget_s

    def bail(last_errors: list[Any]) -> TaskResult:
        emitter.task_failed("task_budget_exceeded", last_errors)
        return TaskResult(ok=False, reason="task_budget_exceeded", last_errors=last_errors)

    # 0. cache lookup. Never return cached source without re-verifying it.
    hit = deps.memory.cache_lookup(prompt)
    if hit is not None:
        if budget_exceeded():
            return bail([])
        vr = deps.tool_client.verify(hit.source)
        if vr.get("ok"):
            emitter.cache_hit(hit.key)
            rr = deps.tool_client.verify(hit.source, run=True)
            emitter.run_output(rr.get("stdout", ""), rr.get("stderr", ""), rr.get("ok", False), rr.get("errors", []))
            citations = [{"file": "verified_cache", "key": hit.key}]
            emitter.task_done(True, hit.iterations, hit.source, citations)
            return TaskResult(ok=True, source=hit.source, iterations=hit.iterations, cached=True, citations=citations)
        # Cache candidate no longer verifies (corpus/verifier drift) -- fall
        # through to normal generation rather than trusting stale source.

    if budget_exceeded():
        return bail([])

    # 1-2. DETERMINISTIC pre-fetch -- not model-chosen. Shared with arm C
    # of the eval runner (eval/runner.py) so "D minus C isolates the
    # verifier loop's contribution" (05_EVAL.md #1) is actually true --
    # both must see identically-good retrieval, or the gap between them
    # measures retrieval-quality drift as well as the loop's effect.
    pf = deterministic_prefetch(prompt, corpus.symbol_names, deps.tool_client, emitter)
    hits, symbols, examples = pf.hits, pf.symbols, pf.examples

    top_failures = deps.memory.top_failures(deps.top_failures_n)
    context = assemble(hits, symbols, examples, top_failures)
    system = system_prompt(corpus.display_name, top_failures_block=_render_top_failures(top_failures))

    # 3-7. generate / verify / repair / behavioral check.
    history: list[HistoryTurn] = []
    last_errors: list[Any] = []

    for i in range(1, deps.max_iter + 1):
        if budget_exceeded():
            return bail(last_errors)

        history_text = render_history(history)
        emitter.model_start(i)
        source = deps.model.generate(
            system, context, prompt, history_text, stream=True, on_token=emitter.model_token
        )
        source = strip_markdown_fences(source)
        emitter.model_done(i, source)

        if budget_exceeded():
            return bail(last_errors)

        emitter.verify_start(i)
        vr = deps.tool_client.verify(source)
        emitter.verify_result(i, vr)

        if not vr.get("ok"):
            last_errors = vr.get("errors", [])
            turn = repair_turn(i, source, vr, deps.tool_client)
            history.append(turn)
            if i < deps.max_iter:
                emitter.repair_start(i + 1, [f"{e.get('code')}@{e.get('line')}" for e in last_errors])
            continue

        # A clean parse only proves the candidate is well-formed, not that
        # it does anything -- run it for real once, both to drive the
        # existing pair-diff check below (if a pair exists) and, always,
        # so the UI has real execution output to show instead of an
        # abstract pass/fail. One call, two purposes -- never run twice.
        if budget_exceeded():
            return bail(last_errors)
        rr = deps.tool_client.verify(source, run=True)
        emitter.run_output(rr.get("stdout", ""), rr.get("stderr", ""), rr.get("ok", False), rr.get("errors", []))

        expected = corpus.expected_for(prompt)
        if expected is not None and rr.get("stdout", "").strip() != expected.strip():
            last_errors = [{"code": "EDIFF", "message": "output did not match expected trace"}]
            turn = diff_turn(i, source, rr, expected)
            history.append(turn)
            if i < deps.max_iter:
                emitter.repair_start(i + 1, ["EDIFF"])
            continue

        deps.memory.record_success(prompt, source, i)
        citations = collect_citations(hits, examples)
        emitter.task_done(True, i, source, citations)
        return TaskResult(ok=True, source=source, iterations=i, citations=citations)

    deps.memory.record_failure(prompt, history)
    emitter.task_failed("max_iterations", last_errors)
    return TaskResult(ok=False, reason="max_iterations", iterations=deps.max_iter, last_errors=last_errors)
