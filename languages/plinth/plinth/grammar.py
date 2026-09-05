"""Shared grammar constants for PLINTH.

Single source of truth. lexer.py, checker.py, runtime.py and symbols.py all
import from here so the emitted `plinth symbols --json` table can never drift
from what the checker actually enforces (01_LANGUAGE.md Sec 7: "Derive the
table from the same constants the checker uses -- never maintain it
separately, or it will drift.").
"""
import math

# --- Structural keywords (16) -----------------------------------------
STRUCTURAL = [
    "define", "scenario", "platform", "sensor", "route", "signal",
    "waypoint", "execute", "end_scenario", "end_platform", "end_sensor",
    "end_route", "end_signal", "end_waypoint", "end_execute", "type",
]

# Reserved but NOT part of the 52-symbol ground-truth table (01_LANGUAGE.md
# Sec 4: the "Full keyword list (52)" is structural+attributes+statements;
# trace/halt/true/false are "Also reserved" -- listed separately, so they
# are excluded from the 52-count but still lexed as reserved words, not
# usable as identifiers).
RESERVED_EXTRA = ["trace", "halt", "true", "false"]

# --- Statements / actions (12) -----------------------------------------
STATEMENTS = {
    "set":        {"valid_parents": ["scenario", "platform", "sensor", "signal", "waypoint"],
                    "arg_shape": "IDENT = value"},
    "bind":       {"valid_parents": ["platform", "sensor"],
                    "arg_shape": "IDENT <- IDENT"},
    "inherit":    {"valid_parents": ["platform"],
                    "arg_shape": "from IDENT"},
    "from":       {"valid_parents": ["platform"],
                    "arg_shape": "(part of inherit)"},
    "at":         {"valid_parents": ["waypoint", "execute"],
                    "arg_shape": "QUANTITY ... (spatial in waypoint, temporal in execute)"},
    "every":      {"valid_parents": ["execute"],
                    "arg_shape": "QUANTITY:time [for QUANTITY:time] action"},
    "for":        {"valid_parents": ["execute"],
                    "arg_shape": "(part of every)"},
    "spawn":      {"valid_parents": ["execute"],
                    "arg_shape": "IDENT [on route IDENT]"},
    "on":         {"valid_parents": ["execute"],
                    "arg_shape": "(part of spawn)"},
    "activate":   {"valid_parents": ["execute"],
                    "arg_shape": "IDENT"},
    "deactivate": {"valid_parents": ["execute"],
                    "arg_shape": "IDENT"},
    "report":     {"valid_parents": ["execute"],
                    "arg_shape": "IDENT"},
}

# --- Attributes (24) -----------------------------------------------------
# dimension: length | time | speed | angle | frequency | power | None
# assign_kind: quantity | bare_int | string | unit_token | reference | position
ATTRIBUTES = {
    "angle_mode":    {"dimension": None,        "assign_kind": "unit_token"},
    "epoch":         {"dimension": "time",      "assign_kind": "quantity"},
    "duration":      {"dimension": "time",      "assign_kind": "quantity"},
    "step":          {"dimension": "time",      "assign_kind": "quantity"},
    "tolerance":     {"dimension": None,        "assign_kind": "bare_int"},
    "label":         {"dimension": None,        "assign_kind": "string"},
    "position":      {"dimension": "angle",     "assign_kind": "position"},
    "altitude":      {"dimension": "length",    "assign_kind": "quantity", "range": (0, 30000)},
    "speed":         {"dimension": "speed",     "assign_kind": "quantity"},
    "heading":       {"dimension": "angle",     "assign_kind": "quantity", "range": (0, 2 * math.pi)},
    "pitch":         {"dimension": "angle",     "assign_kind": "quantity", "range": (-math.pi / 2, math.pi / 2)},
    "roll":          {"dimension": "angle",     "assign_kind": "quantity", "range": (-math.pi, math.pi)},
    "mount":         {"dimension": None,        "assign_kind": "reference"},
    "aperture":      {"dimension": "length",    "assign_kind": "quantity"},
    "gain":          {"dimension": "power",     "assign_kind": "quantity"},
    "noise_floor":   {"dimension": "power",     "assign_kind": "quantity"},
    "range_max":     {"dimension": "length",    "assign_kind": "quantity"},
    "scan_rate":     {"dimension": "frequency", "assign_kind": "quantity"},
    "field_of_view": {"dimension": None,        "assign_kind": "bare_int"},
    "frequency":     {"dimension": "frequency", "assign_kind": "quantity"},
    "bandwidth":     {"dimension": "frequency", "assign_kind": "quantity"},
    "power":         {"dimension": "power",     "assign_kind": "quantity"},
    "modulation":    {"dimension": None,        "assign_kind": "string"},
    "priority":      {"dimension": None,        "assign_kind": "bare_int", "range": (1, 10)},
}

BLOCK_ATTRS = {
    "scenario": {"required": ["duration", "step"],
                 "optional": ["angle_mode", "epoch", "label", "tolerance"]},
    "platform": {"required": ["position"],
                 "optional": ["altitude", "speed", "heading", "pitch", "roll", "label"]},
    "sensor":   {"required": ["mount", "range_max"],
                 "optional": ["aperture", "gain", "noise_floor", "scan_rate",
                              "field_of_view", "priority", "label"]},
    "waypoint": {"required": ["position"],
                 "optional": ["altitude", "speed"]},
    "signal":   {"required": ["frequency"],
                 "optional": ["bandwidth", "power", "modulation", "label"]},
    "route":    {"required": [], "optional": []},
}

PLAT_TYPES = ["air", "ground", "surface", "space"]
SENS_TYPES = ["radar", "eo", "ir", "esm", "acoustic"]

# --- Units ----------------------------------------------------------------
# Ordered longest-first so lexer alternation doesn't stop early (e.g. "min"
# must be tried before "m").
UNITS = ["dbw", "nmi", "khz", "mhz", "mps", "kts", "kph", "deg", "rad",
         "min", "hr", "km", "ft", "hz", "kw", "m", "s", "w"]

UNIT_DIMENSION = {
    "m": "length", "km": "length", "ft": "length", "nmi": "length",
    "s": "time", "min": "time", "hr": "time",
    "mps": "speed", "kts": "speed", "kph": "speed",
    "deg": "angle", "rad": "angle",
    "hz": "frequency", "khz": "frequency", "mhz": "frequency",
    "dbw": "power", "w": "power", "kw": "power",
}

# Multiply a raw value by this factor to get the canonical SI value
# (00_ARCHITECTURE.md Sec 3 doesn't apply here -- this is 01_LANGUAGE.md
# Sec 3: "Canonical internal representation: SI (m, s, mps, rad, hz, w)").
# Simplification: dbw is treated as linearly equal to w (no log10 math) --
# this is a synthetic language, not real RF engineering; documented in the
# language agent's final report.
TO_SI = {
    "m": 1.0, "km": 1000.0, "ft": 0.3048, "nmi": 1852.0,
    "s": 1.0, "min": 60.0, "hr": 3600.0,
    "mps": 1.0, "kts": 0.514444, "kph": 0.277778,
    "deg": math.pi / 180.0, "rad": 1.0,
    "hz": 1.0, "khz": 1000.0, "mhz": 1_000_000.0,
    "dbw": 1.0, "w": 1.0, "kw": 1000.0,
}

# Attributes for which a bare NUMBER (no unit) is legal, per 01_LANGUAGE.md
# Sec 5.4's exception clause (count/priority/field_of_view/step-subdivision,
# where the "step subdivision" case is actually named tolerance in the
# attribute table -- see the language agent's report for this reading).
BARE_INT_ATTRS = {name for name, meta in ATTRIBUTES.items() if meta["assign_kind"] == "bare_int"}


def all_keyword_names():
    """Every reserved word the lexer must not treat as an identifier."""
    return set(STRUCTURAL) | set(STATEMENTS) | set(ATTRIBUTES) | set(RESERVED_EXTRA)
