"""05_EVAL.md: five arms, same 20 tasks, graded by each case's rubric.yaml.

    python -m eval.runner --arm D --corpus plinth --repeat 3
    python -m eval.runner --all-arms --corpus plinth --repeat 3

Every report stamps model name, endpoint, and git SHA (05_EVAL.md #4,
"non-negotiable" -- a number without provenance is worthless).

Arm definitions (05_EVAL.md #1):
  A cold             -- local model, no corpus access, no tools, no loop
  B docs in prompt   -- local model, full docs pasted, no tools, no loop
  C tools, no loop   -- local model, deterministic MCP pre-fetch, no repair
  D full system      -- local model, MCP tools, full generate/verify/repair loop
  E full, cloud      -- same as D, cloud model endpoint (dev-only per
                         00_ARCHITECTURE.md #10; needs credentials this
                         machine does not have -- see runner_help below)

A/B/C are single-shot: one generate call, one grade, no feedback to the
model. D/E run the real `ashlar.harness.loop.run_task`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ashlar.config import REPO_ROOT, Config, load_config, load_corpus_meta
from ashlar.harness.keywords import build_pattern, extract_keywords
from ashlar.harness.loop import Corpus, HarnessDeps, assemble, run_task, strip_markdown_fences
from ashlar.harness.memory import Memory
from ashlar.harness.model import FakeModel, Model, ModelClient
from ashlar.harness.prompts import system_prompt
from ashlar.mcp import server as mcp_server
from ashlar.mcp.client import RealToolClient

CASES_DIR = REPO_ROOT / "eval" / "cases"
REPORTS_DIR = REPO_ROOT / "eval" / "reports"
ARMS = ("A", "B", "C", "D", "E")


@dataclass
class CaseSpec:
    id: str
    task: str
    expected: str | None
    grade: str
    max_iterations: int
    tags: list[str]
    must_contain: list[str]
    must_not_contain: list[str]


def load_cases(cases_dir: Path = CASES_DIR) -> list[CaseSpec]:
    cases = []
    for d in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
        rubric = yaml.safe_load((d / "rubric.yaml").read_text())
        expected_file = d / "expected.txt"
        cases.append(
            CaseSpec(
                id=d.name,
                task=(d / "task.txt").read_text().strip(),
                expected=expected_file.read_text() if expected_file.exists() else None,
                grade=rubric["grade"],
                max_iterations=rubric.get("max_iterations", 4),
                tags=rubric.get("tags", []),
                must_contain=rubric.get("must_contain", []),
                must_not_contain=rubric.get("must_not_contain", []),
            )
        )
    return cases


@dataclass
class CaseResult:
    case_id: str
    arm: str
    ok: bool
    reason: str | None
    iterations: int | None
    tool_calls: int
    wall_clock_s: float
    error_codes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def _grade(source: str | None, tool_client: RealToolClient, case: CaseSpec) -> tuple[bool, str | None, list[str]]:
    """Applies a case's rubric to a candidate source. Returns
    (ok, reason_if_not_ok, error_codes_seen)."""
    if not source:
        return False, "no_source", []
    for needle in case.must_contain:
        if needle not in source:
            return False, f"missing_required_text:{needle!r}", []
    for needle in case.must_not_contain:
        if needle in source:
            return False, f"contains_forbidden_text:{needle!r}", []

    vr = tool_client.verify(source)
    if not vr.get("ok"):
        codes = [e.get("code") for e in vr.get("errors", [])]
        return False, "compile_failed", codes

    if case.grade == "compile_and_run":
        rr = tool_client.verify(source, run=True)
        if not rr.get("ok"):
            codes = [e.get("code") for e in rr.get("errors", [])]
            return False, "run_failed", codes
        if case.expected is not None and rr.get("stdout", "").strip() != case.expected.strip():
            return False, "trace_mismatch", []

    return True, None, []


def _build_single_shot_context(arm: str, prompt: str, corpus: Corpus, tool_client: RealToolClient) -> tuple[str, int]:
    """Arms A/B/C differ only in what `context` the model sees. Returns
    (context, tool_calls_made)."""
    if arm == "A":
        return "", 0

    if arm == "B":
        docs_dir = corpus.meta.root / "docs"
        parts = []
        if docs_dir.is_dir():
            for f in sorted(docs_dir.iterdir()):
                if f.is_file():
                    parts.append(f"# {f.name}\n\n{f.read_text()}")
        return "\n\n".join(parts), 0

    if arm == "C":
        keywords = extract_keywords(prompt, corpus.symbol_names)
        pattern = build_pattern(keywords)
        hits = tool_client.grep_corpus(pattern, limit=12) if pattern else []
        symbols = [tool_client.lookup_symbol(k) for k in keywords[:6]]
        examples = tool_client.get_examples(keywords[0], n=3) if keywords else []
        tool_calls = 1 + len(symbols) + (1 if keywords else 0)
        return assemble(hits, symbols, examples, []), tool_calls

    raise ValueError(f"_build_single_shot_context is only for arms A/B/C, got {arm!r}")


def run_case_single_shot(arm: str, case: CaseSpec, corpus: Corpus, model: ModelClient, tool_client: RealToolClient) -> CaseResult:
    t0 = time.monotonic()
    context, tool_calls = _build_single_shot_context(arm, case.task, corpus, tool_client)
    system = system_prompt(corpus.display_name)
    source = model.generate(system, context, case.task, "", stream=False)
    source = strip_markdown_fences(source)
    ok, reason, codes = _grade(source, tool_client, case)
    return CaseResult(
        # Single-shot arms make exactly one attempt, full stop -- record it
        # as iterations=1 (not None) so "first-attempt pass rate" (a
        # 05_EVAL.md #3 metric with no "D/E only" qualifier, unlike mean
        # iterations) is computable uniformly across all five arms.
        case_id=case.id, arm=arm, ok=ok, reason=reason, iterations=1,
        tool_calls=tool_calls, wall_clock_s=time.monotonic() - t0,
        error_codes=codes, tags=case.tags,
    )


def run_case_looped(arm: str, case: CaseSpec, corpus: Corpus, deps: HarnessDeps) -> CaseResult:
    t0 = time.monotonic()
    events: list[dict[str, Any]] = []
    result = run_task(case.task, corpus, events.append, deps, task_id=f"eval_{arm}_{case.id}")
    tool_calls = sum(1 for e in events if e["type"] == "tool_call")

    ok, reason, codes = result.ok, result.reason, [e.get("code") for e in result.last_errors]
    if ok:
        # Loop already enforced compile (+ run/diff where applicable); still
        # apply must_contain/must_not_contain -- those check *how* a task
        # was solved (e.g. bind vs set), which the loop doesn't know about.
        ok, reason, extra_codes = _grade(result.source, deps.tool_client, case)
        codes = codes or extra_codes

    return CaseResult(
        case_id=case.id, arm=arm, ok=ok, reason=reason, iterations=result.iterations,
        tool_calls=tool_calls, wall_clock_s=time.monotonic() - t0,
        error_codes=codes, tags=case.tags,
    )


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _build_model(cfg: Config, arm: str, cloud_base_url: str | None, cloud_api_key: str | None, cloud_model: str | None) -> ModelClient:
    if arm == "E":
        if not (cloud_base_url and cloud_model):
            raise SystemExit(
                "Arm E needs --cloud-base-url and --cloud-model (and usually "
                "--cloud-api-key) -- see 00_ARCHITECTURE.md #10, cloud endpoints "
                "are dev-only and need real credentials this runner will not guess."
            )
        import dataclasses

        return Model(dataclasses.replace(cfg.model, base_url=cloud_base_url, name=cloud_model, api_key=cloud_api_key or cfg.model.api_key))
    if not cfg.model.name or cfg.model.name == "PENDING_BAKEOFF":
        return FakeModel(responses=[])
    return Model(cfg.model)


def run_arm(
    arm: str, cases: list[CaseSpec], corpus: Corpus, cfg: Config, model: ModelClient, repeat: int, memory_db: Path
) -> list[CaseResult]:
    mcp_server.set_active_corpus(corpus.meta.root.name)
    tool_client = RealToolClient()
    results: list[CaseResult] = []
    for case in cases:
        for _ in range(repeat):
            if arm in ("A", "B", "C"):
                results.append(run_case_single_shot(arm, case, corpus, model, tool_client))
            else:
                memory = Memory(db_path=memory_db)
                deps = HarnessDeps(model=model, tool_client=tool_client, memory=memory, max_iter=case.max_iterations)
                results.append(run_case_looped(arm, case, corpus, deps))
    return results


def summarize(arm: str, results: list[CaseResult]) -> dict[str, Any]:
    n = len(results)
    ok_results = [r for r in results if r.ok]
    verified_rate = len(ok_results) / n if n else 0.0
    wall = [r.wall_clock_s for r in results]
    wall_sorted = sorted(wall)

    def pct(p: float) -> float:
        if not wall_sorted:
            return 0.0
        idx = min(len(wall_sorted) - 1, int(len(wall_sorted) * p))
        return wall_sorted[idx]

    error_hist = Counter(code for r in results for code in r.error_codes if code)
    first_try = sum(1 for r in results if r.ok and r.iterations == 1)
    summary: dict[str, Any] = {
        "arm": arm,
        "n_runs": n,
        "verified_correct_rate": round(verified_rate, 4),
        # A general secondary metric (05_EVAL.md #3), computable for every
        # arm: single-shot arms (A/B/C) always run exactly one attempt, so
        # this collapses to verified_correct_rate for them, which is
        # correct, not a bug -- there is no second attempt to distinguish it from.
        "first_attempt_pass_rate": round(first_try / n, 4) if n else 0.0,
        "wall_clock_p50_s": round(pct(0.5), 2),
        "wall_clock_p95_s": round(pct(0.95), 2),
        "tool_calls_mean": round(statistics.mean(r.tool_calls for r in results), 2) if n else 0.0,
        "error_code_histogram": dict(error_hist.most_common()),
        "unresolved_count": sum(1 for r in results if not r.ok),
    }
    if arm in ("D", "E"):
        # "Mean iterations to verified" is explicitly D/E-only (05_EVAL.md
        # #3) -- A/B/C have no repair loop, so it would trivially always be 1.
        iters = [r.iterations for r in ok_results if r.iterations is not None]
        summary["mean_iterations_to_verified"] = round(statistics.mean(iters), 2) if iters else None
    return summary


def build_report(arms_results: dict[str, list[CaseResult]], cfg: Config, model_endpoints: dict[str, str], repeat: int) -> dict[str, Any]:
    return {
        "git_sha": _git_sha(),
        "timestamp": _now_iso(),
        "corpus": cfg.corpus,
        "repeat": repeat,
        "model_endpoints": model_endpoints,
        "arms": {arm: summarize(arm, results) for arm, results in arms_results.items()},
        "cases_examples_only": summarize(
            "D_examples_only",
            [r for r in arms_results.get("D", []) if "examples_only" in r.tags],
        ) if "D" in arms_results else None,
        "raw": {
            arm: [
                {
                    "case_id": r.case_id, "ok": r.ok, "reason": r.reason,
                    "iterations": r.iterations, "tool_calls": r.tool_calls,
                    "wall_clock_s": round(r.wall_clock_s, 2), "error_codes": r.error_codes,
                    "tags": r.tags,
                }
                for r in results
            ]
            for arm, results in arms_results.items()
        },
    }


def _now_iso() -> str:
    # Wall-clock timestamp for report provenance -- not used for any
    # determinism-sensitive logic, just "when was this run."
    import datetime

    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_report(report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = report["timestamp"].replace(":", "").replace("-", "")
    out = REPORTS_DIR / f"{stamp}.json"
    out.write_text(json.dumps(report, indent=2))
    md_path = out.with_suffix(".md")
    md_path.write_text(render_markdown(report))
    return out


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Eval report -- {report['timestamp']}",
        "",
        f"corpus: `{report['corpus']}`  ·  git: `{report['git_sha'][:12]}`  ·  repeat: {report['repeat']}",
        "",
        "model endpoints: " + ", ".join(f"{a}={ep}" for a, ep in report["model_endpoints"].items()),
        "",
        "| Arm | verified-correct | n | mean iters | first-try | p50 s | p95 s | unresolved |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for arm in ARMS:
        s = report["arms"].get(arm)
        if not s:
            continue
        lines.append(
            f"| {arm} | {s['verified_correct_rate']*100:.0f}% | {s['n_runs']} | "
            f"{s.get('mean_iterations_to_verified', '-')} | "
            f"{(s.get('first_attempt_pass_rate') or 0)*100:.0f}% | "
            f"{s['wall_clock_p50_s']} | {s['wall_clock_p95_s']} | {s['unresolved_count']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--all-arms", action="store_true")
    ap.add_argument("--corpus", default=None, help="defaults to config.yaml's active corpus")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--fake-model", action="store_true", help="use FakeModel (offline runner self-test, no live model needed)")
    ap.add_argument("--fake-responses", nargs="*", default=None, help="canned source strings for --fake-model")
    ap.add_argument("--cloud-base-url", default=None)
    ap.add_argument("--cloud-api-key", default=None)
    ap.add_argument("--cloud-model", default=None)
    args = ap.parse_args()

    if not args.arm and not args.all_arms:
        ap.error("pass --arm A|B|C|D|E or --all-arms")

    cfg = load_config()
    corpus_name = args.corpus or cfg.corpus
    meta = load_corpus_meta(corpus_name)
    mcp_server.set_active_corpus(corpus_name)
    corpus = Corpus.from_disk(meta)
    cases = load_cases()

    arms = list(ARMS) if args.all_arms else [args.arm]
    arms_results: dict[str, list[CaseResult]] = {}
    model_endpoints: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp:
        memory_db = Path(tmp) / "symbols.db"
        for arm in arms:
            if args.fake_model:
                model: ModelClient = FakeModel(responses=args.fake_responses or [])
                model_endpoints[arm] = "fake-model"
            else:
                try:
                    model = _build_model(cfg, arm, args.cloud_base_url, args.cloud_api_key, args.cloud_model)
                except SystemExit as e:
                    # In --all-arms mode, a single arm missing credentials
                    # (arm E, most likely) must not lose every other arm's
                    # already-completed results -- skip it, keep going, and
                    # say so plainly rather than silently dropping it.
                    print(f"=== arm {arm}: SKIPPED -- {e} ===", file=sys.stderr)
                    if args.arm == arm:
                        raise
                    continue
                model_endpoints[arm] = getattr(model, "name", "fake-model")
                if arm == "E":
                    model_endpoints[arm] = f"{args.cloud_base_url} ({args.cloud_model})"
                elif not args.fake_model and isinstance(model, Model):
                    model_endpoints[arm] = f"{cfg.model.base_url} ({cfg.model.name})"

            print(f"=== arm {arm}: {len(cases)} cases x {args.repeat} repeat, model={model_endpoints[arm]} ===", file=sys.stderr)
            t0 = time.monotonic()
            results = run_arm(arm, cases, corpus, cfg, model, args.repeat, memory_db)
            arms_results[arm] = results
            n_ok = sum(1 for r in results if r.ok)
            print(f"    {n_ok}/{len(results)} verified-correct, {time.monotonic()-t0:.1f}s total", file=sys.stderr)

    report = build_report(arms_results, cfg, model_endpoints, args.repeat)
    out_path = write_report(report)
    print(f"wrote {out_path.relative_to(REPO_ROOT)}", file=sys.stderr)
    print(render_markdown(report))


if __name__ == "__main__":
    main()
