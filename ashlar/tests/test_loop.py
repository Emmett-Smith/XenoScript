from pathlib import Path

from ashlar.config import load_corpus_meta
from ashlar.harness.loop import Corpus, HarnessDeps, run_task
from ashlar.harness.memory import Memory
from ashlar.harness.model import FakeModel
from ashlar.harness.subprocess_verify import run_verifier
from ashlar.harness.tool_client import FakeToolClient

FIXTURES = Path(__file__).resolve().parent.parent / "harness" / "fixtures"

# Event types in the order 00_ARCHITECTURE.md #8 / this task's brief prescribes
# for a fail-then-succeed run, ignoring model_token (a high-frequency event not
# part of the named sequence) and collapsing the pre-fetch's repeated
# tool_call/tool_result pairs into the two markers below.
EXPECTED_SKELETON = [
    "task_start",
    "TOOLS",
    "model_start", "model_done", "verify_start", "verify_result",
    "repair_start",
    "model_start", "model_done", "verify_start", "verify_result",
    "run_output",
    "task_done",
]


def _collapse_tool_phase(types: list[str]) -> list[str]:
    """Replaces the initial run of alternating tool_call/tool_result events
    (the deterministic pre-fetch) with a single "TOOLS" marker, so the test
    can assert on the fixed part of the sequence without hardcoding exactly
    how many symbols were prefetched."""
    out = []
    i = 0
    seen_tools = False
    while i < len(types):
        t = types[i]
        if t in ("tool_call", "tool_result"):
            if not seen_tools:
                out.append("TOOLS")
                seen_tools = True
            i += 1
            continue
        if t == "model_token":
            i += 1
            continue
        out.append(t)
        i += 1
    return out


def _make_corpus(meta) -> Corpus:
    return Corpus(
        meta=meta,
        symbol_names=["platform", "altitude"],
        pairs={},
    )


def test_fail_then_succeed_emits_contract_event_sequence(tmp_path):
    model = FakeModel.from_fixtures(FIXTURES, ["attempt1_fail.stub", "attempt2_pass.stub"])
    tool_client = FakeToolClient(
        symbols={"platform": {"found": True, "name": "platform", "kind": "block"}},
        examples={"platform": [{"file": "ex.stub", "start": 1, "end": 3, "text": "define platform p1\nend platform\n", "verified": True}]},
    )
    memory = Memory(tmp_path / "symbols.db")
    meta = load_corpus_meta("stub")
    corpus = _make_corpus(meta)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory, max_iter=4, task_budget_s=300)

    events: list[dict] = []
    result = run_task(
        "define a platform with an altitude of 2000 meters", corpus, events.append, deps, task_id="t_test"
    )

    assert result.ok is True
    assert result.iterations == 2
    assert "FAIL" not in result.source

    types = [e["type"] for e in events]
    assert _collapse_tool_phase(types) == EXPECTED_SKELETON

    # every event carries ts as milliseconds since task_start, monotonically non-decreasing
    ts_values = [e["ts"] for e in events]
    assert ts_values == sorted(ts_values)
    assert events[0]["ts"] == 0 or events[0]["ts"] < 5

    # verify_result events carry ok correctly, in order
    verify_events = [e for e in events if e["type"] == "verify_result"]
    assert [v["ok"] for v in verify_events] == [False, True]

    # task_done carries the final verified source and citations
    done = events[-1]
    assert done["type"] == "task_done"
    assert done["ok"] is True
    assert done["iterations"] == 2
    print("\n".join(f"{e['ts']:>6}ms  {e['type']}" for e in events))


def test_max_iterations_exhausted_emits_task_failed(tmp_path):
    model = FakeModel(responses=["always FAIL this"])
    tool_client = FakeToolClient()
    memory = Memory(tmp_path / "symbols.db")
    corpus = _make_corpus(load_corpus_meta("stub"))
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory, max_iter=4, task_budget_s=300)

    events: list[dict] = []
    result = run_task("a task that will never pass", corpus, events.append, deps)

    assert result.ok is False
    assert result.reason == "max_iterations"
    assert result.iterations == 4
    assert result.last_errors and result.last_errors[0]["code"] == "E041"

    assert events[-1]["type"] == "task_failed"
    assert events[-1]["reason"] == "max_iterations"
    model_starts = [e for e in events if e["type"] == "model_start"]
    assert len(model_starts) == 4  # MAX_ITER respected exactly, not exceeded

    # failure memory was written
    import sqlite3

    con = sqlite3.connect(memory.db_path)
    count = con.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
    con.close()
    assert count > 0


def test_cache_hit_reverifies_before_returning(tmp_path):
    """Hard invariant: no unverified source reaches the user on any code
    path, including cache hits."""
    memory = Memory(tmp_path / "symbols.db")
    memory.record_success("define a platform", "define platform p1\nend platform\n", 1)

    model = FakeModel(responses=["should never be called"])
    tool_client = FakeToolClient()  # default verify_fn: ok unless "FAIL" present
    corpus = _make_corpus(load_corpus_meta("stub"))
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("define a platform", corpus, events.append, deps)

    assert result.ok is True
    assert result.cached is True
    assert model.calls == []  # the model was never invoked -- cache short-circuited generation
    assert tool_client.calls and tool_client.calls[0][0] == "verify"  # but verify WAS called
    assert any(e["type"] == "cache_hit" for e in events)


def test_cache_hit_falls_through_to_generation_when_reverify_fails(tmp_path):
    """If the cached source no longer verifies (corpus/verifier drift), the
    loop must not return it -- it must fall through to normal generation."""
    memory = Memory(tmp_path / "symbols.db")
    memory.record_success("define a platform", "this source now contains FAIL", 1)

    model = FakeModel.from_fixtures(FIXTURES, ["attempt2_pass.stub"])
    tool_client = FakeToolClient()
    corpus = _make_corpus(load_corpus_meta("stub"))
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("define a platform", corpus, events.append, deps)

    assert result.ok is True
    assert result.cached is False
    assert "FAIL" not in result.source
    assert model.calls, "generation must have run once the cached candidate failed reverification"


def test_task_budget_breach_emits_task_failed_without_hanging(tmp_path):
    memory = Memory(tmp_path / "symbols.db")
    model = FakeModel(responses=["irrelevant"])
    tool_client = FakeToolClient()
    corpus = _make_corpus(load_corpus_meta("stub"))
    # Guaranteed-exceeded budget: never let this test depend on timing races.
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory, task_budget_s=-1)

    events: list[dict] = []
    result = run_task("any task", corpus, events.append, deps)

    assert result.ok is False
    assert result.reason == "task_budget_exceeded"
    assert events[-1]["type"] == "task_failed"
    assert events[-1]["reason"] == "task_budget_exceeded"
    assert model.calls == []  # bailed before ever generating


def test_deterministic_prefetch_happens_every_task_even_with_no_pair(tmp_path):
    memory = Memory(tmp_path / "symbols.db")
    model = FakeModel(responses=["define platform p1\nend platform\n"])
    tool_client = FakeToolClient(symbols={"altitude": {"found": True, "name": "altitude", "kind": "attribute"}})
    corpus = _make_corpus(load_corpus_meta("stub"))
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    run_task("set the altitude to 500 meters", corpus, events.append, deps)

    tool_names_called = [c[0] for c in tool_client.calls]
    assert "grep_corpus" in tool_names_called
    assert "lookup_symbol" in tool_names_called
    assert "get_examples" in tool_names_called
    # and it happened before any model call
    first_model_event_idx = next(i for i, e in enumerate(events) if e["type"] == "model_start")
    first_tool_event_idx = next(i for i, e in enumerate(events) if e["type"] == "tool_call")
    assert first_tool_event_idx < first_model_event_idx


def test_end_to_end_against_real_stub_verifier_subprocess(tmp_path):
    """03_HARNESS.md #7 DoD: loop runs end to end against corpora/stub before
    PLINTH exists. This drives the *actual* corpora/stub/verifier.py via
    subprocess, not a reimplementation of its contract."""
    meta = load_corpus_meta("stub")

    def real_verify(source, run, stdin):
        return run_verifier(meta, source, mode="run" if run else "parse", stdin=stdin)

    model = FakeModel.from_fixtures(FIXTURES, ["attempt1_fail.stub", "attempt2_pass.stub"])
    tool_client = FakeToolClient(verify_fn=real_verify)
    memory = Memory(tmp_path / "symbols.db")
    corpus = _make_corpus(meta)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("define a platform with an altitude", corpus, events.append, deps)

    assert result.ok is True
    assert result.iterations == 2
    verify_results = [e for e in events if e["type"] == "verify_result"]
    assert [v["ok"] for v in verify_results] == [False, True]
    assert verify_results[0]["errors"][0]["code"] == "E041"


def test_markdown_fenced_output_is_stripped_before_verify(tmp_path):
    """Phase 2 integration finding: qwen2.5-coder:3b wraps output in a
    markdown fence despite prompts/system.md explicitly forbidding it, and
    repeats the identical fenced output on every repair iteration since the
    error (E001 on the backtick) never points it at the real problem. The
    harness must not trust the model to follow that instruction -- strip
    one leading/trailing fence before it ever reaches verify()."""
    meta = load_corpus_meta("stub")

    def real_verify(source, run, stdin):
        return run_verifier(meta, source, mode="run" if run else "parse", stdin=stdin)

    fenced = "```plinth\nthis is clean source with no errors\n```"
    model = FakeModel(responses=[fenced])
    tool_client = FakeToolClient(verify_fn=real_verify)
    memory = Memory(tmp_path / "symbols.db")
    corpus = _make_corpus(meta)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("say hello", corpus, events.append, deps)

    assert result.ok is True
    assert result.iterations == 1
    assert result.source == "this is clean source with no errors"
    model_done = next(e for e in events if e["type"] == "model_done")
    assert model_done["source"] == "this is clean source with no errors"


def test_prefetch_grep_gives_every_keyword_a_fair_share_not_just_the_first(tmp_path):
    """Phase 2 live-model diagnosis: a single combined grep_corpus call
    (one alternation pattern, one shared limit) let a generic, ubiquitous
    keyword ("platform" appears in nearly every file) exhaust the limit
    entirely before a rarer, far more diagnostic keyword (a specific
    identifier the file actually turned out to hinge on) ever got a
    single hit. The pre-fetch must query per keyword with a fair-share
    limit each, so a specific identifier's hit survives alongside a
    generic keyword's many hits, not instead of them."""
    meta = load_corpus_meta("stub")
    model = FakeModel(responses=["clean output, no FAIL literal here"])
    tool_client = FakeToolClient(
        grep_hits={
            "platform": [
                {"file": "examples/a.stub", "line": i, "text": f"platform line {i}", "kind": "example"}
                for i in range(1, 7)
            ],
            "uav_01": [
                {"file": "examples/special.stub", "line": 1, "text": "uav_01 the specific one", "kind": "example"}
            ],
        }
    )
    memory = Memory(tmp_path / "symbols.db")
    corpus = Corpus(meta=meta, symbol_names=["platform"], pairs={})
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    run_task("configure platform uav_01", corpus, events.append, deps)

    grep_calls = [kwargs for name, kwargs in tool_client.calls if name == "grep_corpus"]
    patterns_queried = {c["pattern"] for c in grep_calls}
    assert len(grep_calls) > 1, "expected one grep_corpus call per keyword, not one combined call"
    assert "uav_01" in patterns_queried

    tool_results = [e for e in events if e["type"] == "tool_result" and e["tool"] == "grep_corpus"]
    all_previewed_files = {p.get("file") for r in tool_results for p in r["preview"]}
    assert "examples/special.stub" in all_previewed_files, (
        "the specific keyword's hit was crowded out of every grep_corpus tool_result preview"
    )


def test_run_output_event_carries_real_execution_stdout(tmp_path):
    """00_ARCHITECTURE.md #8: `run_output` exists so the UI can show real
    program execution output, not just a parse pass/fail. Must fire once
    per successful task, with the real stdout from actually running the
    verified source -- not the compile-only verify() result."""
    meta = load_corpus_meta("stub")

    def verify_fn(source, run, stdin):
        if "FAIL" in source:
            return {"ok": False, "errors": [{"code": "E041", "line": 1, "message": "no"}],
                    "warnings": [], "stdout": "", "stderr": "", "exit_code": 1, "duration_ms": 1}
        return {"ok": True, "errors": [], "warnings": [], "stdout": "real program output\n" if run else "",
                "stderr": "", "exit_code": 0, "duration_ms": 1}

    model = FakeModel(responses=["clean source"])
    tool_client = FakeToolClient(verify_fn=verify_fn)
    memory = Memory(tmp_path / "symbols.db")
    corpus = _make_corpus(meta)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("say hello", corpus, events.append, deps)

    assert result.ok is True
    run_events = [e for e in events if e["type"] == "run_output"]
    assert len(run_events) == 1
    assert run_events[0]["stdout"] == "real program output\n"
    assert run_events[0]["ok"] is True
    # run_output must land before task_done, not after
    types = [e["type"] for e in events]
    assert types.index("run_output") < types.index("task_done")


def test_cache_hit_also_emits_run_output(tmp_path):
    meta = load_corpus_meta("stub")

    def verify_fn(source, run, stdin):
        return {"ok": True, "errors": [], "warnings": [], "stdout": "cached run output\n" if run else "",
                "stderr": "", "exit_code": 0, "duration_ms": 1}

    tool_client = FakeToolClient(verify_fn=verify_fn)
    memory = Memory(tmp_path / "symbols.db")
    memory.record_success("say hello", "clean source", 1)
    corpus = _make_corpus(meta)
    deps = HarnessDeps(model=FakeModel(responses=[]), tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("say hello", corpus, events.append, deps)

    assert result.cached is True
    run_events = [e for e in events if e["type"] == "run_output"]
    assert len(run_events) == 1
    assert run_events[0]["stdout"] == "cached run output\n"


def test_run_output_carries_the_reason_when_compile_passes_but_run_cannot(tmp_path):
    """A compile-clean program can still have nothing runnable (e.g.
    PLINTH's real "no scenario defined; nothing to run" for a bare
    platform block) -- a real, expected outcome, not a harness bug. The
    UI needs the reason, not a silent empty box next to a green verdict."""
    meta = load_corpus_meta("stub")

    def verify_fn(source, run, stdin):
        if not run:
            return {"ok": True, "errors": [], "warnings": [], "stdout": "",
                     "stderr": "", "exit_code": 0, "duration_ms": 1}
        return {
            "ok": False,
            "errors": [{"file": None, "line": None, "col": None, "code": "EHARNESS",
                        "message": "no scenario defined; nothing to run", "severity": "error"}],
            "warnings": [], "stdout": "", "stderr": "", "exit_code": 1, "duration_ms": 1,
        }

    model = FakeModel(responses=["clean source"])
    tool_client = FakeToolClient(verify_fn=verify_fn)
    memory = Memory(tmp_path / "symbols.db")
    corpus = _make_corpus(meta)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task("just a platform, no scenario", corpus, events.append, deps)

    assert result.ok is True  # compile still passed
    run_events = [e for e in events if e["type"] == "run_output"]
    assert len(run_events) == 1
    assert run_events[0]["ok"] is False
    assert run_events[0]["errors"][0]["message"] == "no scenario defined; nothing to run"


# ---------------------------------------------------------------------------
# Behavioral check (00_ARCHITECTURE.md #9 step 7): a 97% similarity
# threshold, not exact match, per explicit human direction.
# ---------------------------------------------------------------------------


def _make_corpus_with_pair(meta, prompt: str, expected: str) -> Corpus:
    from ashlar.harness.memory import normalize_task

    return Corpus(meta=meta, symbol_names=[], pairs={normalize_task(prompt): expected})


def test_behavioral_check_accepts_near_miss_output_above_97_percent_similar(tmp_path):
    meta = load_corpus_meta("stub")
    expected = "[t=0.000] scenario demo start step=1.000 duration=10.000\n[t=10.000] scenario end status=ok\n"
    # A trailing-zero formatting difference in the middle of the string
    # (survives .strip(), so this is a genuine near-miss, not an
    # accidentally-exact match) -- 98.9% similar by difflib ratio,
    # above the 97% threshold. Must be accepted without a repair round.
    almost = expected.replace("duration=10.000", "duration=10.00 ")

    def verify_fn(source, run, stdin):
        if not run:
            return {"ok": True, "errors": [], "warnings": [], "stdout": "",
                     "stderr": "", "exit_code": 0, "duration_ms": 1}
        return {"ok": True, "errors": [], "warnings": [], "stdout": almost,
                "stderr": "", "exit_code": 0, "duration_ms": 1}

    model = FakeModel(responses=["clean source"])
    tool_client = FakeToolClient(verify_fn=verify_fn)
    memory = Memory(tmp_path / "symbols.db")
    prompt = "run the demo scenario"
    corpus = _make_corpus_with_pair(meta, prompt, expected)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task(prompt, corpus, events.append, deps)

    assert result.ok is True
    assert result.iterations == 1  # accepted first try, no repair triggered


def test_behavioral_check_rejects_genuinely_different_output_below_97_percent(tmp_path):
    meta = load_corpus_meta("stub")
    expected = "[t=0.000] scenario demo start step=1.000 duration=10.000\n[t=10.000] scenario end status=ok\n"
    wrong = "completely different trace content that shares almost nothing with the real one\n"

    def verify_fn(source, run, stdin):
        if not run:
            return {"ok": True, "errors": [], "warnings": [], "stdout": "",
                     "stderr": "", "exit_code": 0, "duration_ms": 1}
        return {"ok": True, "errors": [], "warnings": [], "stdout": wrong,
                "stderr": "", "exit_code": 0, "duration_ms": 1}

    model = FakeModel(responses=["clean source"])
    tool_client = FakeToolClient(verify_fn=verify_fn)
    memory = Memory(tmp_path / "symbols.db")
    prompt = "run the demo scenario"
    corpus = _make_corpus_with_pair(meta, prompt, expected)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task(prompt, corpus, events.append, deps)

    assert result.ok is False
    assert result.reason == "max_iterations"
    verify_results = [e for e in events if e["type"] == "verify_result"]
    assert all(v["ok"] for v in verify_results)  # compiled fine every time
    # ...but never accepted, because the run output never matched closely enough


def test_behavioral_check_never_accepts_empty_output_regardless_of_similarity_math(tmp_path):
    """Guards against a degenerate case: an empty actual output vs. a
    short expected string can score a misleadingly high difflib ratio.
    "Keep running until it produces an output" means empty must never
    pass, full stop, regardless of what the ratio math says."""
    meta = load_corpus_meta("stub")
    expected = "ok\n"

    def verify_fn(source, run, stdin):
        return {"ok": True, "errors": [], "warnings": [], "stdout": "",
                "stderr": "", "exit_code": 0, "duration_ms": 1}

    model = FakeModel(responses=["clean source"] * 4)
    tool_client = FakeToolClient(verify_fn=verify_fn)
    memory = Memory(tmp_path / "symbols.db")
    prompt = "run the demo scenario"
    corpus = _make_corpus_with_pair(meta, prompt, expected)
    deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory)

    events: list[dict] = []
    result = run_task(prompt, corpus, events.append, deps)

    assert result.ok is False
