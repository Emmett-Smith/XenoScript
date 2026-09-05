import re

from ashlar.ingest.indexer import Bm25Index, build_index, tokenize


def test_underscore_identifiers_tokenize_as_a_single_token():
    # The silent retrieval-quality killer called out explicitly in
    # specs/02_BACKEND.md #1: a naive word tokenizer must NOT split
    # noise_floor / end_platform into ["noise", "floor"] etc.
    assert tokenize("noise_floor") == ["noise_floor"]
    assert tokenize("end_platform") == ["end_platform"]
    assert tokenize("set noise_floor to end_platform now") == [
        "set",
        "noise_floor",
        "to",
        "end_platform",
        "now",
    ]
    # Prove the underlying claim about Python's \w+ directly, rather than
    # trusting the docstring.
    assert re.findall(r"\w+", "noise_floor") == ["noise_floor"]


def test_hyphenated_identifiers_tokenize_as_a_single_token():
    # Same class of bug, different corpus: found live against COBOL's real
    # idiomatic identifier convention (WS-INDEX, CUSTOMER-NAME), which a
    # tokenizer built only for PLINTH's underscore convention split into
    # spurious halves ("WS" and "INDEX" as two "symbols").
    assert tokenize("ws-index") == ["ws-index"]
    assert tokenize("customer-name") == ["customer-name"]
    assert tokenize("move customer-name to ws-index now") == [
        "move",
        "customer-name",
        "to",
        "ws-index",
        "now",
    ]
    # A lone/trailing hyphen (subtraction, a range dash) must not be
    # absorbed into a neighboring token.
    assert tokenize("a - b") == ["a", "b"]
    assert tokenize("total - 1") == ["total", "1"]


def test_tokenize_lowercases():
    assert tokenize("NOISE_FLOOR") == ["noise_floor"]


def test_bm25_search_ranks_relevant_entry_higher():
    entries = [
        {"kind": "doc", "file": "a.md", "text": "the noise_floor attribute controls background level"},
        {"kind": "doc", "file": "b.md", "text": "unrelated content about something else entirely"},
    ]
    index = build_index(entries, bm25_weight=1.0)
    results = index.search("noise_floor", top_n=5)
    assert results[0]["file"] == "a.md"


def test_bm25_search_kind_filter():
    entries = [
        {"kind": "doc", "file": "a.md", "text": "noise_floor appears here in docs"},
        {"kind": "example", "file": "b.stub", "text": "noise_floor 10"},
    ]
    index = build_index(entries, bm25_weight=1.0)
    doc_only = index.search("noise_floor", top_n=5, kind="doc")
    assert all(r["kind"] == "doc" for r in doc_only)
    example_only = index.search("noise_floor", top_n=5, kind="example")
    assert all(r["kind"] == "example" for r in example_only)


def test_bm25_weight_scales_score():
    entries = [{"kind": "doc", "file": "a.md", "text": "noise_floor attribute"}]
    unweighted = build_index(entries, bm25_weight=1.0).search("noise_floor")[0]["score"]
    weighted = build_index(entries, bm25_weight=0.5).search("noise_floor")[0]["score"]
    assert weighted == unweighted * 0.5


def test_bm25_index_empty_corpus_does_not_raise():
    index = build_index([], bm25_weight=0.75)
    assert index.search("anything") == []


def test_bm25_save_and_load_round_trip(tmp_path):
    entries = [{"kind": "doc", "file": "a.md", "text": "noise_floor attribute"}]
    index = build_index(entries, bm25_weight=0.75)
    path = tmp_path / "bm25.pkl"
    index.save(path)
    loaded = Bm25Index.load(path)
    assert loaded.bm25_weight == 0.75
    results = loaded.search("noise_floor")
    assert results and results[0]["file"] == "a.md"
