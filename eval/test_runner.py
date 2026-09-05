"""05_EVAL.md #8 DoD: "verify the runner against FakeModel" -- this is that
verification. No live model, no network, fast."""

from __future__ import annotations

from collections import Counter

from ashlar.config import load_corpus_meta
from ashlar.harness.loop import Corpus
from ashlar.harness.model import FakeModel
from ashlar.mcp import server as mcp_server
from eval.runner import ARMS, load_cases, run_arm, summarize


def test_load_cases_matches_the_prescribed_category_distribution():
    """05_EVAL.md #2's table: 4 basic, 4 gotchas, 3 examples-only,
    3 composition, 3 repair, 3 behavioral = 20."""
    cases = load_cases()
    assert len(cases) == 20
    category_counts = Counter(c.tags[0] for c in cases)
    assert category_counts == {
        "basic": 4,
        "gotcha": 4,
        "examples_only": 3,
        "composition": 3,
        "repair": 3,
        "behavioral": 3,
    }


def test_behavioral_cases_have_expected_txt_and_compile_and_run_grade():
    cases = load_cases()
    behavioral = [c for c in cases if c.grade == "compile_and_run"]
    assert len(behavioral) == 3
    for c in behavioral:
        assert c.expected is not None and c.expected.strip()


def test_runner_offline_self_test_against_fake_model(tmp_path):
    """Runs every arm against a FakeModel with zero network access and
    confirms the runner doesn't crash and produces sane summaries -- the
    grading logic itself (does this pass this rubric) is exercised for
    real against the real PLINTH verifier; only the model is fake."""
    cfg_corpus = "plinth"
    meta = load_corpus_meta(cfg_corpus)
    mcp_server.set_active_corpus(cfg_corpus)
    corpus = Corpus.from_disk(meta)
    cases = load_cases()[:3]  # keep this test fast; full 20 is exercised manually

    clean_source = "define scenario x\n  set duration = 10s\n  set step = 1s\nend_scenario\n"

    for arm in ARMS:
        if arm == "E":
            continue  # needs cloud credentials, covered by a separate explicit test
        model = FakeModel(responses=[clean_source])
        from ashlar.config import load_config

        results = run_arm(arm, cases, corpus, load_config(), model, repeat=1, memory_db=tmp_path / "symbols.db")
        assert len(results) == len(cases)
        summary = summarize(arm, results)
        assert 0.0 <= summary["verified_correct_rate"] <= 1.0
        assert summary["n_runs"] == len(cases)


def test_arm_e_without_cloud_credentials_fails_loudly_not_silently():
    from ashlar.config import load_config
    from eval.runner import _build_model

    cfg = load_config()
    try:
        _build_model(cfg, "E", None, None, None)
        raised = False
    except SystemExit:
        raised = True
    assert raised, "arm E with no cloud endpoint configured must refuse to silently fall back"
