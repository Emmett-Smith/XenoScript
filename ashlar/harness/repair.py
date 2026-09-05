"""Repair-turn context assembly. 03_HARNESS.md #1: "Repair quality drives
your headline number. Spend effort here."

Per error, we assemble:
- the error line plus surrounding source, with line numbers
- the full error message verbatim
- `lookup_symbol` output for any identifier named in the error message
- for E020/E021/E022 specifically, `get_examples("bind", 2)` -- those codes
  are the corpus's binding gotchas; "bind" is an error-code-triggered
  literal from the spec, not a language name, so it does not violate the
  corpus-agnostic invariant (00_ARCHITECTURE.md #3).

History discipline (03_HARNESS.md #1, load-bearing): do NOT resend the full
conversation verbatim each iteration. Every `HistoryTurn` carries both a
one-line `summary` ("attempt 1: E041 at line 14") and a full `detail` block
(rendered from `prompts/repair.md`). `render_history` sends the full
`detail` only for the most recent turn and collapses every earlier turn to
its one-liner. This is what keeps prompt size bounded across iterations
instead of growing with MAX_ITER.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ashlar.harness.prompts import repair_prompt
from ashlar.harness.tool_client import ToolClient

CONTEXT_LINES_BEFORE = 3
CONTEXT_LINES_AFTER = 3
_QUOTED_IDENT_RE = re.compile(r"'([A-Za-z_][A-Za-z0-9_]*)'|\"([A-Za-z_][A-Za-z0-9_]*)\"")
BIND_CODES = {"E020", "E021", "E022"}
MAX_IDENTIFIER_LOOKUPS_PER_ERROR = 3


@dataclass
class HistoryTurn:
    iteration: int
    source: str
    errors: list[dict[str, Any]]
    summary: str
    detail: str


def _line_window(source: str, line: int) -> str:
    lines = source.splitlines()
    if not lines:
        return "(empty source)"
    lo = max(1, line - CONTEXT_LINES_BEFORE)
    hi = min(len(lines), line + CONTEXT_LINES_AFTER)
    out = []
    for n in range(lo, hi + 1):
        marker = ">> " if n == line else "   "
        out.append(f"{marker}{n:>4} | {lines[n - 1]}")
    return "\n".join(out)


def _identifiers_in_message(message: str) -> list[str]:
    idents = []
    for m in _QUOTED_IDENT_RE.finditer(message):
        idents.append(m.group(1) or m.group(2))
    return idents[:MAX_IDENTIFIER_LOOKUPS_PER_ERROR]


def _format_symbol_lookup(name: str, result: dict[str, Any]) -> str:
    if not result.get("found"):
        return f"  {name}: not found in symbol table"
    parts = [f"  {name}: kind={result.get('kind')}"]
    if result.get("valid_parents"):
        parts.append(f"valid_parents={result['valid_parents']}")
    if result.get("arg_shape"):
        parts.append(f"arg_shape={result['arg_shape']}")
    if result.get("dimension"):
        parts.append(f"dimension={result['dimension']}")
    return " ".join(parts)


def format_error_block(source: str, error: dict[str, Any]) -> str:
    """The error line/message/context portion of a single error -- no
    symbol lookups here, those are collected separately into the
    `Reference:` section (see `_build_reference`)."""
    line = error.get("line") or 1
    code = error.get("code") or "?"
    message = error.get("message") or ""
    return f"[{code}] line {line}: {message}\n{_line_window(source, line)}"


def _build_reference(errors: list[dict[str, Any]], tool_client: ToolClient) -> tuple[str, list[str]]:
    """Aggregates `lookup_symbol` results for every identifier named across
    all errors in this turn, plus `get_examples('bind', 2)` if any error is
    a binding gotcha (E020/E021/E022). Returns (rendered block, names looked up)."""
    seen: list[str] = []
    lines: list[str] = []
    has_bind_code = False

    for err in errors:
        if (err.get("code") or "") in BIND_CODES:
            has_bind_code = True
        for name in _identifiers_in_message(err.get("message") or ""):
            if name in seen:
                continue
            seen.append(name)
            result = tool_client.lookup_symbol(name)
            lines.append(_format_symbol_lookup(name, result))

    if has_bind_code:
        for ex in tool_client.get_examples("bind", 2):
            lines.append(f"  example ({ex.get('file')}:{ex.get('start')}-{ex.get('end')}):\n{ex.get('text', '')}")

    return "\n".join(lines) if lines else "(none)", seen


def _summarize(iteration: int, errors: list[dict[str, Any]]) -> str:
    if not errors:
        return f"attempt {iteration}: unknown failure"
    first = errors[0]
    tail = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
    return f"attempt {iteration}: {first.get('code')} at line {first.get('line')}{tail}"


def repair_turn(iteration: int, source: str, verify_result: dict[str, Any], tool_client: ToolClient) -> HistoryTurn:
    errors = verify_result.get("errors", [])
    errors_with_context = "\n\n".join(format_error_block(source, err) for err in errors) or "(none)"
    symbol_lookups, _ = _build_reference(errors, tool_client)

    detail = repair_prompt(
        current_source=source,
        errors_with_context=errors_with_context,
        symbol_lookups=symbol_lookups,
    )
    return HistoryTurn(
        iteration=iteration,
        source=source,
        errors=errors,
        summary=_summarize(iteration, errors),
        detail=detail,
    )


def diff_turn(iteration: int, source: str, run_result: dict[str, Any], expected: str) -> HistoryTurn:
    """Behavioral mismatch turn (00_ARCHITECTURE.md #9 step 7): source parsed
    clean but its executed trace didn't match the expected output for a
    pair task."""
    actual = run_result.get("stdout", "")
    detail = (
        "Your previous attempt compiled but produced the wrong output when run.\n"
        "Fix the logic, not the syntax.\n\n"
        "Current source:\n" + source + "\n\n"
        f"Expected output:\n{expected}\n\nActual output:\n{actual}"
    )
    synthetic_error = {"code": "EDIFF", "line": None, "message": "output did not match expected trace"}
    return HistoryTurn(
        iteration=iteration,
        source=source,
        errors=[synthetic_error],
        summary=f"attempt {iteration}: EDIFF (output mismatch)",
        detail=detail,
    )


def render_history(history: list[HistoryTurn]) -> str:
    """Bounded-size rendering: all-but-last turn collapse to one-liners,
    only the most recent turn's full detail is included. This is what makes
    prompt growth sub-linear across MAX_ITER iterations instead of resending
    the whole conversation."""
    if not history:
        return ""
    prior = history[:-1]
    last = history[-1]
    lines = []
    if prior:
        lines.append("Prior attempts:")
        lines.extend(f"- {t.summary}" for t in prior)
        lines.append("")
    lines.append(last.detail)
    return "\n".join(lines)
