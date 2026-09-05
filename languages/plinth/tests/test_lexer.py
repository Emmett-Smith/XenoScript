import pytest

from lexer import tokenize, PlinthError


def kinds(tokens):
    return [t.kind for t in tokens if t.kind != "EOF"]


def test_quantity_no_space_is_one_token():
    toks = tokenize("1500m")
    assert kinds(toks) == ["QUANTITY"]
    assert toks[0].value == (1500.0, "m")


def test_negative_quantity():
    toks = tokenize("-100.10deg")
    assert toks[0].kind == "QUANTITY"
    assert toks[0].value == (-100.10, "deg")


def test_bare_number_alone_is_number():
    toks = tokenize("42")
    assert kinds(toks) == ["NUMBER"]
    assert toks[0].value == 42.0


def test_space_between_number_and_unit_is_e043():
    with pytest.raises(PlinthError) as exc:
        tokenize("1500 m")
    assert exc.value.code == "E043"


def test_bare_number_not_followed_by_unit_is_fine():
    # "5 " followed by something that is not a unit word at all.
    toks = tokenize("5 apples")
    assert kinds(toks) == ["NUMBER", "IDENT"]


def test_min_not_confused_with_m_plus_in():
    # regression: unit alternation must try "min" before "m"
    toks = tokenize("10min")
    assert toks[0].value == (10.0, "min")


def test_identifier_with_unit_like_prefix_stays_identifier():
    toks = tokenize("mount")
    assert toks[0].kind == "KEYWORD"
    assert toks[0].value == "mount"


def test_keywords_vs_identifiers():
    toks = tokenize("define uav_01")
    assert toks[0].kind == "KEYWORD"
    assert toks[1].kind == "IDENT"


def test_true_false_are_bool_not_ident():
    toks = tokenize("true false")
    assert kinds(toks) == ["BOOL", "BOOL"]
    assert toks[0].value is True
    assert toks[1].value is False


def test_string_literal():
    toks = tokenize('"hello world"')
    assert toks[0].kind == "STRING"
    assert toks[0].value == "hello world"


def test_comment_is_skipped():
    toks = tokenize("define # a comment\nplatform")
    assert kinds(toks) == ["KEYWORD", "KEYWORD"]


def test_arrow_token():
    toks = tokenize("<-")
    assert toks[0].kind == "ARROW"


def test_unexpected_character_is_e001():
    with pytest.raises(PlinthError) as exc:
        tokenize("@")
    assert exc.value.code == "E001"
