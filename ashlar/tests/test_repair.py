from ashlar.harness.repair import (
    format_error_block,
    render_history,
    repair_turn,
)
from ashlar.harness.tool_client import FakeToolClient

SOURCE = "\n".join(f"line {n}" for n in range(1, 11))  # 10 lines


def test_format_error_block_includes_line_numbers_and_message_verbatim():
    error = {"line": 5, "code": "E041", "message": "dimensional mismatch: field 'altitude'"}
    block = format_error_block(SOURCE, error)
    assert "dimensional mismatch: field 'altitude'" in block
    assert "[E041] line 5" in block
    assert ">>    5 | line 5" in block  # error line marked
    assert "   2 | line 2" in block  # context before
    assert "   8 | line 8" in block  # context after


def test_format_error_block_clamps_at_source_boundaries():
    error = {"line": 1, "code": "E999", "message": "boom"}
    block = format_error_block(SOURCE, error)
    assert "0 |" not in block  # never a fabricated line 0


def test_repair_turn_looks_up_identifiers_named_in_error_message():
    client = FakeToolClient(symbols={"altitude": {"found": True, "name": "altitude", "kind": "attribute"}})
    vr = {"ok": False, "errors": [{"line": 2, "code": "E041", "message": "bad dimension on 'altitude'"}]}
    turn = repair_turn(1, SOURCE, vr, client)
    assert "altitude" in turn.detail
    assert any(call[0] == "lookup_symbol" and call[1]["name"] == "altitude" for call in client.calls)


def test_repair_turn_pulls_bind_examples_for_gotcha_codes():
    client = FakeToolClient(examples={"bind": [{"file": "ex.plth", "start": 1, "end": 3, "text": "bind x to y"}]})
    vr = {"ok": False, "errors": [{"line": 2, "code": "E020", "message": "missing bind"}]}
    turn = repair_turn(1, SOURCE, vr, client)
    assert any(call[0] == "get_examples" and call[1]["symbol"] == "bind" for call in client.calls)
    assert "bind x to y" in turn.detail


def test_repair_turn_summary_is_one_line():
    client = FakeToolClient()
    vr = {"ok": False, "errors": [{"line": 14, "code": "E041", "message": "m"}]}
    turn = repair_turn(1, SOURCE, vr, client)
    assert turn.summary == "attempt 1: E041 at line 14"
    assert "\n" not in turn.summary


def test_render_history_empty():
    assert render_history([]) == ""


def test_render_history_collapses_all_but_last_to_one_liners():
    client = FakeToolClient()
    turns = []
    for i in range(1, 4):
        vr = {"ok": False, "errors": [{"line": i, "code": "E041", "message": f"error number {i}"}]}
        turns.append(repair_turn(i, SOURCE, vr, client))

    rendered = render_history(turns)
    # Only the last turn's full detail (with its own error message) is present in full...
    assert "error number 3" in rendered
    # ...earlier turns show up only as one-liners, not their full detail text
    assert "attempt 1: E041 at line 1" in rendered
    assert "attempt 2: E041 at line 2" in rendered
    # the one-liner form appears, but the *repeated full detail* for turns 1
    # and 2 (their own repair.md preamble) should not appear twice
    assert rendered.count("Your previous attempt failed to compile") == 1


def test_history_rendering_does_not_grow_linearly_across_iterations():
    """03_HARNESS.md #7 DoD: assert token/char count does not grow linearly.
    Each additional iteration should add roughly one summary line, not a
    full repeated transcript."""
    client = FakeToolClient()
    turns = []
    lengths = []
    for i in range(1, 5):
        vr = {"ok": False, "errors": [{"line": i, "code": "E041", "message": "a fairly detailed error message " * 5}]}
        turns.append(repair_turn(i, SOURCE, vr, client))
        lengths.append(len(render_history(turns)))

    # If history were resent verbatim, each step would add a full detail
    # block (~hundreds of chars). Bounded growth means the *increment*
    # between steps stays small and roughly constant (one summary line),
    # not proportional to the cumulative detail size resent so far.
    increments = [lengths[i] - lengths[i - 1] for i in range(1, len(lengths))]
    for inc in increments:
        assert inc < 120, f"increment {inc} suggests full history is being resent"
