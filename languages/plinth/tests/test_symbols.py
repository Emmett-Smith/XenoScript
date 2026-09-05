import symbols as S
from grammar import STRUCTURAL, ATTRIBUTES, STATEMENTS


def test_symbol_count_is_52():
    table = S.build_symbol_table()
    assert len(table) == 52
    assert len(STRUCTURAL) + len(ATTRIBUTES) + len(STATEMENTS) == 52


def test_every_symbol_has_required_fields():
    table = S.build_symbol_table()
    for sym in table:
        assert "name" in sym
        assert "kind" in sym
        assert "valid_parents" in sym
        assert "arg_shape" in sym


def test_examples_only_features_are_reported():
    table = S.build_symbol_table()
    names = {s["name"] for s in table}
    assert "inherit" in names
    assert "every" in names
    assert "for" in names


def test_altitude_symbol_matches_architecture_example_shape():
    table = S.build_symbol_table()
    alt = next(s for s in table if s["name"] == "altitude")
    assert alt["kind"] == "attribute"
    assert alt["dimension"] == "length"
    assert alt["range"] == [0, 30000]
    assert "platform" in alt["valid_parents"]


def test_payload_has_language_field():
    payload = S.build_symbols_payload()
    assert payload["language"] == "plinth"
    assert len(payload["symbols"]) == 52
