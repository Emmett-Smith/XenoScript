"""PLINTH checker: symbol resolution, unit dimension checking, attribute
legality (01_LANGUAGE.md Sec 4, Sec 5, Sec 6).

Single-pass, first-error-wins (see parser.py docstring for the rationale).
Produces a `World` object consumed by runtime.py and by cli.py.

Reading choices made here (documented for the Phase-2 lead, since these
fill gaps the spec leaves implicit):

- `mount` (required sensor attribute) is a reference to the platform the
  sensor is mounted on, assigned via `bind mount <- <platform>` -- never
  `set`. This is what lets `plinth run` print "activate radar_a on uav_01"
  in the trace without a separate grammar production for it, and it makes
  `bind`'s valid_parents = [platform, sensor] (given verbatim in
  00_ARCHITECTURE's symbols.py example) actually do something on the
  sensor side.
- Declaration-before-reference (01_LANGUAGE.md Sec 2 design target) is
  enforced for every plain identifier reference (inherit target, spawn
  platform/route, activate/deactivate/report target) -- not just
  `inherit`. Only `bind` may point forward (Sec 5.1: "so it may point
  forward"). A reference to a name defined later => E012; to a name never
  defined => E011.
- E070-E072 are deliberately NOT raised here; they are runtime-only
  (raised during simulation in runtime.py), matching how 01_LANGUAGE.md
  Sec 6 separates "Runtime:" codes from the rest and TASKS.md tracks them
  as a distinct checklist item after `parse` lands.
"""
import math

from lexer import PlinthError
from grammar import (
    ATTRIBUTES, BLOCK_ATTRS, UNIT_DIMENSION, TO_SI,
)
import parser as P


class World:
    """Resolved program, ready for the runtime or for introspection."""

    def __init__(self):
        self.scenario = None          # dict: name, duration_si, step_si, angle_mode, label
        self.platforms = {}           # name -> dict(attrs..., si..., type)
        self.sensors = {}             # name -> dict(attrs..., mount, type)
        self.routes = {}              # name -> list of waypoint dicts
        self.signals = {}             # name -> dict(attrs...)
        self.execute_blocks = []      # list of ExecuteBlock AST nodes
        self.angle_mode = "deg"
        self.names = {}                # name -> kind


def _fmt_num(x):
    if x == int(x):
        return str(int(x))
    return f"{x:g}"


def _fix_hint(attr, block_kind):
    meta = ATTRIBUTES[attr]
    if attr == "position":
        return "position at <lat> <lon>"
    if meta["assign_kind"] == "reference":
        return f"bind {attr} <- <identifier>"
    if meta["assign_kind"] == "unit_token":
        return f"set {attr} = deg   (or rad)"
    if meta["assign_kind"] == "bare_int":
        return f"set {attr} = <integer>"
    if meta["assign_kind"] == "string":
        return f'set {attr} = "..."'
    return f"set {attr} = <quantity:{meta['dimension']}>"


def _valid_attrs_msg(block_kind):
    req = BLOCK_ATTRS[block_kind]["required"]
    opt = BLOCK_ATTRS[block_kind]["optional"]
    return f"valid here: {', '.join(req + opt) or '(none)'}"


def _determine_angle_mode(program):
    for tl in program.toplevels:
        if isinstance(tl, P.ScenarioDef):
            for stmt in tl.stmts:
                if isinstance(stmt, P.SetStmt) and stmt.attr == "angle_mode":
                    if stmt.value_kind == "ident" and stmt.value in ("deg", "rad"):
                        return stmt.value
                    raise PlinthError(
                        "E003", stmt.line, stmt.col,
                        f"invalid angle_mode value; expected 'deg' or 'rad'",
                    )
    return "deg"


def _prepass_names(program):
    """First pass: collect every top-level identifier and its kind, so
    forward-reference checks (E011 vs E012) can tell "never defined" from
    "defined later"."""
    names = {}
    kind_map = {
        P.ScenarioDef: "scenario", P.PlatformDef: "platform",
        P.SensorDef: "sensor", P.RouteDef: "route", P.SignalDef: "signal",
    }
    for tl in program.toplevels:
        kind = kind_map.get(type(tl))
        if kind is None:
            continue  # ExecuteBlock has no name
        if tl.name in names:
            first_line = names[tl.name][1]
            raise PlinthError(
                "E010", tl.line, tl.col,
                f"identifier '{tl.name}' already defined at line {first_line}; "
                f"choose a different name for this {kind}",
            )
        names[tl.name] = (kind, tl.line)
    return names


def _check_value(attr, value_kind, value, block_kind, angle_mode, line, col):
    """Validate a (value_kind, value) pair against attr's declared shape.
    Returns the canonical-SI value (or the raw value for string/reference).
    Raises PlinthError on mismatch."""
    meta = ATTRIBUTES[attr]

    if attr == "angle_mode":
        if value_kind == "ident" and value in ("deg", "rad"):
            return value
        raise PlinthError("E003", line, col,
                           f"invalid angle_mode value; expected 'deg' or 'rad'")

    if value_kind == "ident":
        raise PlinthError(
            "E022", line, col,
            f"'set' used on reference '{attr}'; use 'bind {attr} <- {value}' instead",
        )

    kind = meta["assign_kind"]

    if kind == "bare_int":
        if value_kind == "number":
            si = value
        elif value_kind == "quantity":
            num, unit = value
            raise PlinthError(
                "E041", line, col,
                f"dimensional mismatch: field '{attr}' expects a bare integer, "
                f"got a quantity with unit '{unit}'; write 'set {attr} = {_fmt_num(num)}' "
                f"with no unit",
            )
        else:
            raise PlinthError(
                "E041", line, col,
                f"dimensional mismatch: field '{attr}' expects a bare integer, got {value_kind}",
            )
    elif kind == "quantity":
        if value_kind == "number":
            raise PlinthError(
                "E040", line, col,
                f"missing unit on numeric literal for '{attr}'; expected a "
                f"{meta['dimension']} quantity, e.g. 'set {attr} = {_fmt_num(value)}"
                f"{_example_unit(meta['dimension'])}'",
            )
        elif value_kind == "quantity":
            num, unit = value
            dim = UNIT_DIMENSION.get(unit)
            if dim != meta["dimension"]:
                raise PlinthError(
                    "E041", line, col,
                    f"dimensional mismatch: field '{attr}' expects {meta['dimension']}, "
                    f"got {dim} ({unit})",
                )
            if dim == "angle" and unit != angle_mode:
                raise PlinthError(
                    "E042", line, col,
                    f"angle unit '{unit}' conflicts with scenario angle_mode "
                    f"'{angle_mode}'; write 'set {attr} = {_fmt_num(num)}{angle_mode}' "
                    f"or change the scenario's angle_mode",
                )
            si = num * TO_SI[unit]
            if "range" in meta:
                lo, hi = meta["range"]
                if not (lo - 1e-9 <= si <= hi + 1e-9):
                    raise PlinthError(
                        "E060", line, col,
                        f"value {num}{unit} for '{attr}' is out of permitted range "
                        f"[{_fmt_num(lo)}, {_fmt_num(hi)}] ({meta['dimension']})",
                    )
        else:
            raise PlinthError(
                "E041", line, col,
                f"dimensional mismatch: field '{attr}' expects a {meta['dimension']} "
                f"quantity, got {value_kind}",
            )
    elif kind == "string":
        if value_kind != "string":
            raise PlinthError(
                "E041", line, col,
                f"dimensional mismatch: field '{attr}' expects a string literal, "
                f"got {value_kind}",
            )
        si = value
    elif kind == "reference":
        raise PlinthError(
            "E022", line, col,
            f"'set' used on reference '{attr}'; use 'bind {attr} <- ...' instead",
        )
    else:
        raise PlinthError("E001", line, col, f"cannot assign to '{attr}' with 'set'")
    return si


def _example_unit(dimension):
    return {"length": "m", "time": "s", "speed": "mps", "angle": "deg",
            "frequency": "hz", "power": "w"}.get(dimension, "")


def _check_position(stmt, angle_mode):
    for label, q in (("lat", stmt.lat), ("lon", stmt.lon)):
        num, unit = q
        dim = UNIT_DIMENSION.get(unit)
        if dim != "angle":
            raise PlinthError(
                "E041", stmt.line, stmt.col,
                f"dimensional mismatch: field 'position' expects angle, got {dim} ({unit})",
            )
        if unit != angle_mode:
            raise PlinthError(
                "E042", stmt.line, stmt.col,
                f"angle unit '{unit}' conflicts with scenario angle_mode "
                f"'{angle_mode}'; write '{label}' using '{angle_mode}'",
            )
    lat_si = stmt.lat[0] * TO_SI[stmt.lat[1]]
    lon_si = stmt.lon[0] * TO_SI[stmt.lon[1]]
    if not (-math.pi / 2 - 1e-9 <= lat_si <= math.pi / 2 + 1e-9):
        raise PlinthError("E060", stmt.line, stmt.col,
                           f"latitude {stmt.lat[0]}{stmt.lat[1]} out of range [-90, 90] deg")
    if not (-math.pi - 1e-9 <= lon_si <= math.pi + 1e-9):
        raise PlinthError("E060", stmt.line, stmt.col,
                           f"longitude {stmt.lon[0]}{stmt.lon[1]} out of range [-180, 180] deg")
    return lat_si, lon_si


def _process_block(block_kind, name, stmts, angle_mode, pending_binds, block_line):
    """Process a platform/sensor/scenario/signal/waypoint body. Returns
    (attrs, refs) where attrs maps attribute name -> resolved SI/raw value,
    and refs maps arbitrary bind labels -> target identifier."""
    attrs = {}
    attrs_seen_line = {}
    refs = {}
    refs_seen_line = {}
    legal = set(BLOCK_ATTRS[block_kind]["required"]) | set(BLOCK_ATTRS[block_kind]["optional"])

    for stmt in stmts:
        if isinstance(stmt, P.SetStmt):
            attr = stmt.attr
            if attr not in ATTRIBUTES:
                if stmt.value_kind == "ident":
                    raise PlinthError(
                        "E022", stmt.line, stmt.col,
                        f"'set' used on reference '{attr}'; use "
                        f"'bind {attr} <- {stmt.value}' instead",
                    )
                raise PlinthError(
                    "E050", stmt.line, stmt.col,
                    f"unknown attribute '{attr}' for {block_kind}; {_valid_attrs_msg(block_kind)}",
                )
            if attr not in legal:
                raise PlinthError(
                    "E051", stmt.line, stmt.col,
                    f"attribute '{attr}' not permitted in {block_kind}; "
                    f"{_valid_attrs_msg(block_kind)}",
                )
            if attr in attrs_seen_line:
                raise PlinthError(
                    "E010", stmt.line, stmt.col,
                    f"attribute '{attr}' already set on this {block_kind} at line "
                    f"{attrs_seen_line[attr]}; remove the duplicate 'set {attr}'",
                )
            si = _check_value(attr, stmt.value_kind, stmt.value, block_kind,
                               angle_mode, stmt.line, stmt.col)
            attrs[attr] = si
            attrs_seen_line[attr] = stmt.line

        elif isinstance(stmt, P.BindStmt):
            lhs = stmt.name
            if lhs in ("position", "angle_mode"):
                raise PlinthError(
                    "E001", stmt.line, stmt.col,
                    f"'{lhs}' cannot be set with 'bind'; use "
                    f"'{_fix_hint(lhs, block_kind)}' instead",
                )
            if lhs in ATTRIBUTES:
                if ATTRIBUTES[lhs]["assign_kind"] != "reference":
                    raise PlinthError(
                        "E001", stmt.line, stmt.col,
                        f"'{lhs}' cannot be set with 'bind'; use "
                        f"'{_fix_hint(lhs, block_kind)}' instead",
                    )
                if lhs not in legal:
                    raise PlinthError(
                        "E051", stmt.line, stmt.col,
                        f"attribute '{lhs}' not permitted in {block_kind}; "
                        f"{_valid_attrs_msg(block_kind)}",
                    )
                if lhs in attrs_seen_line:
                    raise PlinthError(
                        "E010", stmt.line, stmt.col,
                        f"attribute '{lhs}' already set on this {block_kind} at line "
                        f"{attrs_seen_line[lhs]}; remove the duplicate 'bind {lhs}'",
                    )
                attrs[lhs] = stmt.target
                attrs_seen_line[lhs] = stmt.line
            else:
                if lhs in refs_seen_line:
                    raise PlinthError(
                        "E010", stmt.line, stmt.col,
                        f"reference '{lhs}' already bound on this {block_kind} at line "
                        f"{refs_seen_line[lhs]}; remove the duplicate 'bind {lhs}'",
                    )
                refs[lhs] = stmt.target
                refs_seen_line[lhs] = stmt.line
            pending_binds.append((stmt.target, stmt.line, stmt.col))

        elif isinstance(stmt, P.PositionStmt):
            if "position" not in legal:
                raise PlinthError(
                    "E051", stmt.line, stmt.col,
                    f"attribute 'position' not permitted in {block_kind}; "
                    f"{_valid_attrs_msg(block_kind)}",
                )
            if "position" in attrs_seen_line:
                raise PlinthError(
                    "E010", stmt.line, stmt.col,
                    f"attribute 'position' already set on this {block_kind} at line "
                    f"{attrs_seen_line['position']}; remove the duplicate 'position at'",
                )
            lat_si, lon_si = _check_position(stmt, angle_mode)
            attrs["position"] = (lat_si, lon_si)
            attrs_seen_line["position"] = stmt.line

        elif isinstance(stmt, P.InheritStmt):
            pass  # handled by caller (needs cross-block ordering info)

        else:  # pragma: no cover - defensive
            raise PlinthError("E001", block_line, 1, f"unexpected statement in {block_kind}")

    return attrs, refs, attrs_seen_line


def _check_required(block_kind, name, attrs, attrs_seen_line, block_line):
    for attr in BLOCK_ATTRS[block_kind]["required"]:
        if attr not in attrs:
            raise PlinthError(
                "E052", block_line, 1,
                f"required attribute '{attr}' missing for {block_kind} '{name}'; "
                f"add '{_fix_hint(attr, block_kind)}'",
            )


def check_program(program):
    world = World()
    world.angle_mode = _determine_angle_mode(program)
    names = _prepass_names(program)
    world.names = names

    resolved_so_far = {}   # name -> kind, filled in as each block finishes
    pending_binds = []      # (target, line, col) to check for E020 at the end

    for tl in program.toplevels:
        if isinstance(tl, P.ScenarioDef):
            attrs, refs, seen = _process_block(
                "scenario", tl.name, tl.stmts, world.angle_mode, pending_binds, tl.line)
            _check_required("scenario", tl.name, attrs, seen, tl.line)
            world.scenario = {
                "name": tl.name,
                "duration_si": attrs.get("duration"),
                "step_si": attrs.get("step"),
                "angle_mode": world.angle_mode,
                "label": attrs.get("label"),
                "epoch_si": attrs.get("epoch"),
                "tolerance": attrs.get("tolerance"),
            }
            resolved_so_far[tl.name] = "scenario"

        elif isinstance(tl, P.PlatformDef):
            base_attrs = {}
            for stmt in tl.stmts:
                if isinstance(stmt, P.InheritStmt):
                    target = stmt.target
                    kind_line = names.get(target)
                    if kind_line is None:
                        raise PlinthError(
                            "E011", stmt.line, stmt.col,
                            f"reference to undefined identifier '{target}' in "
                            f"'inherit from {target}'",
                        )
                    if kind_line[0] != "platform":
                        raise PlinthError(
                            "E011", stmt.line, stmt.col,
                            f"'{target}' is not a platform; 'inherit from' requires "
                            f"a previously defined platform",
                        )
                    if target not in world.platforms:
                        raise PlinthError(
                            "E012", stmt.line, stmt.col,
                            f"forward reference not permitted here: platform "
                            f"'{target}' is defined after '{tl.name}' (line "
                            f"{kind_line[1]}); move '{target}' above '{tl.name}', "
                            f"or use bind for a deferred reference instead",
                        )
                    base_attrs.update(world.platforms[target]["attrs"])

            attrs, refs, seen = _process_block(
                "platform", tl.name, tl.stmts, world.angle_mode, pending_binds, tl.line)
            merged = dict(base_attrs)
            merged.update(attrs)
            _check_required("platform", tl.name, merged, seen, tl.line)
            world.platforms[tl.name] = {
                "type": tl.plat_type, "attrs": merged, "refs": refs, "line": tl.line,
            }
            resolved_so_far[tl.name] = "platform"

        elif isinstance(tl, P.SensorDef):
            attrs, refs, seen = _process_block(
                "sensor", tl.name, tl.stmts, world.angle_mode, pending_binds, tl.line)
            _check_required("sensor", tl.name, attrs, seen, tl.line)
            world.sensors[tl.name] = {
                "type": tl.sens_type, "attrs": attrs, "refs": refs,
                "mount": attrs.get("mount"), "line": tl.line,
            }
            resolved_so_far[tl.name] = "sensor"

        elif isinstance(tl, P.RouteDef):
            waypoints = []
            for wp in tl.waypoints:
                attrs, refs, seen = _process_block(
                    "waypoint", tl.name, wp.stmts, world.angle_mode, pending_binds, wp.line)
                _check_required("waypoint", tl.name, attrs, seen, wp.line)
                waypoints.append(attrs)
            world.routes[tl.name] = waypoints
            resolved_so_far[tl.name] = "route"

        elif isinstance(tl, P.SignalDef):
            attrs, refs, seen = _process_block(
                "signal", tl.name, tl.stmts, world.angle_mode, pending_binds, tl.line)
            _check_required("signal", tl.name, attrs, seen, tl.line)
            world.signals[tl.name] = {"attrs": attrs, "line": tl.line}
            resolved_so_far[tl.name] = "signal"

        elif isinstance(tl, P.ExecuteBlock):
            _check_execute_refs(tl, names, resolved_so_far)
            world.execute_blocks.append(tl)

    for target, line, col in pending_binds:
        if target not in names:
            raise PlinthError(
                "E020", line, col,
                f"unresolved bind: '{target}' is never defined anywhere in this file",
            )

    return world


def _check_execute_refs(execute_block, names, resolved_so_far):
    for stmt in execute_block.stmts:
        action = getattr(stmt, "action", None)
        if action is None:
            continue
        _check_action_refs(action, names, resolved_so_far)


def _check_action_refs(action, names, resolved_so_far):
    targets = []
    if isinstance(action, P.SpawnAction):
        targets.append((action.platform, "platform"))
        if action.route is not None:
            targets.append((action.route, "route"))
    elif isinstance(action, (P.ActivateAction, P.DeactivateAction, P.ReportAction)):
        targets.append((action.ident, None))
    else:
        return

    for target, expect_kind in targets:
        kind_line = names.get(target)
        if kind_line is None:
            raise PlinthError(
                "E011", action.line, action.col,
                f"reference to undefined identifier '{target}'",
            )
        if expect_kind is not None and kind_line[0] != expect_kind:
            raise PlinthError(
                "E011", action.line, action.col,
                f"'{target}' is not a {expect_kind}",
            )
        if target not in resolved_so_far:
            raise PlinthError(
                "E012", action.line, action.col,
                f"forward reference not permitted here: '{target}' is defined "
                f"after this point (line {kind_line[1]}); move its definition "
                f"earlier, or use bind for a deferred reference",
            )
