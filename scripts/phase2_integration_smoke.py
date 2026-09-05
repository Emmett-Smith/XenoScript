#!/usr/bin/env python3
"""Phase 2 integration proof (specs/ORCHESTRATOR.md Phase 2 exit criterion):
run one task prompt -> retrieval -> generation -> failed verify -> repair ->
verified, against the REAL PLINTH corpus (not corpora/stub), through the
REAL MCP tool functions (ashlar.mcp.client.RealToolClient), with a
FakeModel scripted to fail iteration 1 and succeed iteration 2. Confirms the
repair path actually engages end to end, and writes the full event stream
to a file a human (or the frontend agent, as a fixture) can read.

Usage: uv run python scripts/phase2_integration_smoke.py
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

BROKEN_SOURCE = """define platform uav_f type air
  position at 40.0deg 120.0deg
  set altitude = 1500 m
end_platform
"""

FIXED_SOURCE = """define platform uav_f type air
  position at 40.0deg 120.0deg
  set altitude = 1500m
end_platform
"""


def main() -> None:
    meta = load_corpus_meta("plinth")
    mcp_server.set_active_corpus("plinth")
    corpus = Corpus.from_disk(meta)

    with tempfile.TemporaryDirectory() as tmp:
        memory = Memory(db_path=Path(tmp) / "symbols.db")
        deps = HarnessDeps(
            model=FakeModel(responses=[BROKEN_SOURCE, FIXED_SOURCE]),
            tool_client=RealToolClient(),
            memory=memory,
        )

        events: list[dict] = []
        prompt = (
            "Give platform uav_f an altitude of exactly fifteen hundred meters, "
            "written the way PLINTH expects a quantity to be written."
        )
        result = run_task(prompt, corpus, events.append, deps, task_id="phase2_smoke")

    out_dir = REPO_ROOT / "eval" / "fixtures" / "event_streams"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "phase2_fail_then_repair.jsonl"
    out_path.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    print(f"TaskResult: ok={result.ok} iterations={result.iterations} reason={result.reason}")
    print(f"Wrote {len(events)} events to {out_path.relative_to(REPO_ROOT)}")
    print()
    print("Event type sequence:")
    for e in events:
        extra = ""
        if e["type"] == "verify_result":
            extra = f" ok={e['ok']}"
            if not e["ok"]:
                extra += f" errors={[(x.get('code'), x.get('line')) for x in e['errors']]}"
        print(f"  {e['ts']:>6}ms  {e['type']}{extra}")

    assert result.ok, "Phase 2 exit criterion FAILED: task did not end verified"
    assert result.iterations == 2, f"expected repair to take exactly 2 iterations, got {result.iterations}"
    verify_results = [e for e in events if e["type"] == "verify_result"]
    assert not verify_results[0]["ok"], "expected iteration 1 to fail verification"
    assert verify_results[0]["errors"][0]["code"] == "E043", "expected the spacing gotcha (E043) on iteration 1"
    assert verify_results[1]["ok"], "expected iteration 2 to pass verification"
    print()
    print("Phase 2 exit criterion MET: prompt -> retrieval -> generation -> "
          "failed verify (E043) -> repair -> verified, against real PLINTH.")


if __name__ == "__main__":
    main()
