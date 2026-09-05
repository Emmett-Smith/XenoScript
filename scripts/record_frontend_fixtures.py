#!/usr/bin/env python3
"""Records additional real event-stream fixtures for the frontend agent
(specs/ORCHESTRATOR.md Phase 3: "feed it recorded event streams from
Phase 2 as fixtures... every panel must be driven by real events, reject
any mocked data path"). All three streams below are produced by actually
running ashlar.harness.loop.run_task against the real PLINTH corpus and
the real sandbox -- nothing here is hand-written JSON.

scripts/phase2_integration_smoke.py already wrote
eval/fixtures/event_streams/phase2_fail_then_repair.jsonl (fail iter 1 on
a real E043, repair, verified iter 2). This script adds the other two
states the frontend's verdict block needs to exercise:
  - immediate_pass.jsonl      (generating -> verified, no repair)
  - max_iterations_exhausted.jsonl (repairing repeatedly -> task_failed)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ashlar.config import load_corpus_meta  # noqa: E402
from ashlar.harness.loop import Corpus, HarnessDeps, run_task  # noqa: E402
from ashlar.harness.memory import Memory  # noqa: E402
from ashlar.harness.model import FakeModel  # noqa: E402
from ashlar.mcp import server as mcp_server  # noqa: E402
from ashlar.mcp.client import RealToolClient  # noqa: E402

OUT_DIR = REPO_ROOT / "eval" / "fixtures" / "event_streams"

CLEAN_SOURCE = """define scenario tiny_run
  set duration = 10s
  set step = 1s
end_scenario
"""

# Always-broken: unknown keyword, never resolves in MAX_ITER=4 attempts.
ALWAYS_BROKEN = "definitely not plinth source\n"


def record(name: str, prompt: str, responses: list[str]) -> None:
    meta = load_corpus_meta("plinth")
    mcp_server.set_active_corpus("plinth")
    corpus = Corpus.from_disk(meta)
    with tempfile.TemporaryDirectory() as tmp:
        memory = Memory(db_path=Path(tmp) / "symbols.db")
        deps = HarnessDeps(
            model=FakeModel(responses=responses),
            tool_client=RealToolClient(),
            memory=memory,
        )
        events: list[dict] = []
        result = run_task(prompt, corpus, events.append, deps, task_id=name)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{name}.jsonl"
    out_path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    print(f"{name}: ok={result.ok} iterations={result.iterations} "
          f"reason={result.reason} -> {len(events)} events -> {out_path.relative_to(REPO_ROOT)}")


def main() -> None:
    record(
        "immediate_pass",
        "Write a scenario called tiny_run that runs for 10 seconds with a 1 second step.",
        [CLEAN_SOURCE],
    )
    record(
        "max_iterations_exhausted",
        "Write something that will never compile, on purpose, for a fixture.",
        [ALWAYS_BROKEN] * 4,
    )


if __name__ == "__main__":
    main()
