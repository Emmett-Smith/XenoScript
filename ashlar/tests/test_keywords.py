from ashlar.harness.keywords import build_pattern, extract_keywords

SYMBOL_NAMES = [
    "altitude", "platform", "waypoint", "sensor", "bind", "inherit",
    "noise_floor", "end_platform", "execute",
]


def test_symbol_matches_rank_first():
    kws = extract_keywords("set the altitude on the platform to 2000 meters", SYMBOL_NAMES)
    assert kws[0] in {"altitude", "platform"}
    assert "altitude" in kws and "platform" in kws


def test_quoted_strings_are_included():
    kws = extract_keywords('bind sensor to "coastal_radar"', SYMBOL_NAMES)
    assert "coastal_radar" in kws


def test_underscore_identifiers_are_single_tokens():
    kws = extract_keywords("why does noise_floor differ from end_platform here", SYMBOL_NAMES)
    assert "noise_floor" in kws
    assert "end_platform" in kws
    # must not have been split into "noise" / "floor"
    assert "noise" not in kws
    assert "floor" not in kws


def test_falls_back_to_rarest_tokens_by_doc_frequency_when_no_real_match():
    # Only 2-letter words: too short to match the identifier-pattern stage,
    # no symbol-table hits, no quotes -> forces the doc-frequency fallback.
    doc_freq = {"ok": 500, "go": 400, "up": 3, "hi": 12}
    kws = extract_keywords("ok go up hi", [], doc_freq=doc_freq)
    assert kws == ["up", "hi", "go"]  # rarest-first, top 3


def test_fallback_with_no_doc_freq_source_still_returns_something():
    kws = extract_keywords("ok go up hi", [])
    assert 0 < len(kws) <= 3


def test_normal_sentence_does_not_need_fallback():
    kws = extract_keywords("please configure the sensor carefully", SYMBOL_NAMES)
    assert "sensor" in kws


def test_build_pattern_is_regex_safe_alternation():
    pattern = build_pattern(["altitude", "end_platform"])
    import re

    re.compile(pattern)  # must not raise
    assert "altitude" in pattern and "end_platform" in pattern


def test_extract_keywords_handles_empty_prompt():
    assert extract_keywords("", SYMBOL_NAMES) == []


def test_contractions_are_not_mistaken_for_quoted_strings():
    """Phase 2 live-model diagnosis: a real eval task phrased with two
    contractions ("I've seen ... even though I can't find it") produced a
    single garbage ~90-char "keyword" spanning both apostrophes, which then
    dominated the grep_corpus pattern. A bare apostrophe touching a letter
    on either side must never be read as a quote delimiter."""
    kws = extract_keywords(
        "I know I've seen a shorthand for this even though I can't find it in the manual",
        SYMBOL_NAMES,
    )
    assert not any(len(k) > 20 for k in kws), f"a garbage multi-word span leaked through: {kws}"


def test_real_quoted_string_still_extracted_alongside_a_contraction():
    kws = extract_keywords("I've heard of the 'inherit' shorthand", SYMBOL_NAMES)
    assert "inherit" in kws
