"""05_EVAL.md #8 DoD: "verify the runner against FakeModel" -- this is that
verification. No live model, no network, fast."""

from __future__ import annotations

from collections import Counter

from ashlar.config import REPO_ROOT, load_corpus_meta
from ashlar.harness.loop import Corpus
from ashlar.harness.model import FakeModel
from ashlar.mcp import server as mcp_server
from eval.runner import ARMS, build_report, cases_dir_for, load_cases, run_arm, summarize


def test_build_report_records_the_corpus_actually_tested_not_configs_default():
    """Real bug found live: build_report recorded cfg.corpus (config.yaml's
    static default, "plinth") instead of the corpus --corpus actually
    tested. Ran a COBOL sweep on a machine still configured to default to
    plinth, and the report came back labeled "plinth" -- the frontend's
    baseline chart then rendered COBOL's real numbers under the PLINTH
    header on screen. cfg.corpus stays "plinth" here on purpose, to prove
    corpus_name (not cfg) is what ends up in the report."""
    from ashlar.config import load_config

    cfg = load_config()
    assert cfg.corpus == "plinth"  # the actual default this bug depended on
    report = build_report({}, cfg, {}, repeat=1, corpus_name="cobol")
    assert report["corpus"] == "cobol"


def test_build_report_falls_back_to_cfg_corpus_when_none_given():
    from ashlar.config import load_config

    cfg = load_config()
    report = build_report({}, cfg, {}, repeat=1)
    assert report["corpus"] == cfg.corpus


def test_cases_dir_for_falls_back_to_flat_dir_when_no_per_corpus_set_exists():
    # PLINTH has no eval/cases/plinth/ subdirectory -- it's the original
    # flat set, and must keep resolving there unchanged.
    assert cases_dir_for("plinth") == REPO_ROOT / "eval" / "cases"
    assert cases_dir_for(None) == REPO_ROOT / "eval" / "cases"
    assert cases_dir_for("nonexistent_corpus") == REPO_ROOT / "eval" / "cases"


def test_cases_dir_for_prefers_a_real_per_corpus_set_when_present():
    cobol_dir = REPO_ROOT / "eval" / "cases" / "cobol"
    if cobol_dir.is_dir() and any(cobol_dir.iterdir()):
        assert cases_dir_for("cobol") == cobol_dir


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
