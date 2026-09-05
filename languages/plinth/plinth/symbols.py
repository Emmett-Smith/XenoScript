"""Emit PLINTH's grammar as ground truth JSON (01_LANGUAGE.md Sec 7).

Derived entirely from grammar.py -- the same constants checker.py enforces
-- so this can never drift from the actual behavior of the interpreter.
Emits all 52 keywords (structural + attributes + statements); trace/halt/
true/false are reserved but intentionally excluded from the 52-count (see
grammar.py's RESERVED_EXTRA docstring).

Reports `inherit` and `every`/`for` (01_LANGUAGE.md Sec 8's examples-only
features) exactly like every other symbol -- this is the deliberate
asymmetry with the docs, which never mention them.
"""
from grammar import (
    STRUCTURAL, STATEMENTS, ATTRIBUTES, BLOCK_ATTRS, UNIT_DIMENSION,
)


def _attribute_symbol(name, meta):
    valid_parents = sorted(
        block for block, spec in BLOCK_ATTRS.items()
        if name in spec["required"] or name in spec["optional"]
    )
    required_in = sorted(
        block for block, spec in BLOCK_ATTRS.items() if name in spec["required"]
    )
    if meta["assign_kind"] == "quantity":
        arg_shape = f"<quantity:{meta['dimension']}>"
    elif meta["assign_kind"] == "bare_int":
        arg_shape = "<int>"
    elif meta["assign_kind"] == "string":
        arg_shape = "<string>"
    elif meta["assign_kind"] == "unit_token":
        arg_shape = "deg | rad"
    elif meta["assign_kind"] == "reference":
        arg_shape = "IDENT <- IDENT"
    elif meta["assign_kind"] == "position":
        arg_shape = "at <quantity:angle> <quantity:angle>"
    else:  # pragma: no cover
        arg_shape = "?"
    sym = {
        "name": name,
        "kind": "attribute",
        "valid_parents": valid_parents,
        "arg_shape": arg_shape,
        "dimension": meta["dimension"],
        "required": bool(required_in),
        "required_in": required_in,
    }
    if "range" in meta:
        sym["range"] = list(meta["range"])
    return sym


def build_symbol_table():
    symbols = []
    for name in STRUCTURAL:
        symbols.append({
            "name": name,
            "kind": "structural",
            "valid_parents": [],
            "arg_shape": "",
        })
    for name, meta in ATTRIBUTES.items():
        symbols.append(_attribute_symbol(name, meta))
    for name, meta in STATEMENTS.items():
        symbols.append({
            "name": name,
            "kind": "statement",
            "valid_parents": meta["valid_parents"],
            "arg_shape": meta["arg_shape"],
        })
    return symbols


def build_symbols_payload():
    return {"language": "plinth", "symbols": build_symbol_table()}
