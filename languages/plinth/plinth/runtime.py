"""PLINTH runtime: deterministic tick execution + trace emission.

Trace format is fixed 3-decimal, no wall-clock timestamps, diffable
(01_LANGUAGE.md Sec 7 "Runtime trace format"). Position lat/lon are
printed with 4 decimals (matching 00_ARCHITECTURE.md Sec 5's example line
`pos=45.2000,-100.1000` verbatim); everything else uses 3 decimals.

Design choices (no wall-clock physics simulator exists to consult, so
these are the language agent's calls, documented for Phase 2):

- `report` always reports `detections=0` -- there is no real sensor model,
  and 0 is the only value that keeps traces exactly reproducible.
- `every T [for W]` fires at t = T, 2T, 3T, ... up to min(W or duration,
  duration). First fire is at T, not 0 (matching `at T` firing once at T).
- Events scheduled beyond the scenario's duration are silently not
  executed (no error) since nothing in 01_LANGUAGE.md forbids it.
- `halt` is only legal at or after the scenario duration; firing it
  earlier is E070 (01_LANGUAGE.md Sec 6). In practice this makes `halt`
  mostly a trap for models that try to end a scenario "early".
"""
import math

from lexer import PlinthError
from grammar import TO_SI
import parser as P


def _round3(x):
    return round(x + 1e-9, 3)


def simulate(world):
    """Returns (trace_lines: list[str]). Raises PlinthError (E070/E071/E072)
    on a runtime violation; trace_lines collected so far is available on
    the exception via .partial_trace."""
    scenario = world.scenario
    name = scenario["name"]
    duration = scenario["duration_si"]
    step = scenario["step_si"]

    lines = []
    lines.append(
        f"[t=0.000] scenario {name} start step={step:.3f} duration={duration:.3f}"
    )

    events = []  # (t, seq, action)
    seq = 0
    for block in world.execute_blocks:
        for stmt in block.stmts:
            if isinstance(stmt, P.ExecAt):
                t = _round3(stmt.time[0] * TO_SI[stmt.time[1]])
                events.append((t, seq, stmt.action))
                seq += 1
            elif isinstance(stmt, P.ExecEvery):
                period = stmt.period[0] * TO_SI[stmt.period[1]]
                limit = duration
                if stmt.for_window is not None:
                    window = stmt.for_window[0] * TO_SI[stmt.for_window[1]]
                    limit = min(duration, window)
                t = period
                while t <= limit + 1e-9:
                    events.append((_round3(t), seq, stmt.action))
                    seq += 1
                    t += period

    events.sort(key=lambda e: (e[0], e[1]))

    spawned = set()
    active = set()

    try:
        for t, _, action in events:
            if t > duration + 1e-9:
                continue
            if isinstance(action, P.SpawnAction):
                if action.platform in spawned:
                    raise PlinthError(
                        "E072", action.line, action.col,
                        f"spawn of already-spawned platform '{action.platform}'; "
                        f"remove the duplicate spawn or spawn a different platform",
                    )
                spawned.add(action.platform)
                plat = world.platforms[action.platform]
                lat_si, lon_si = plat["attrs"]["position"]
                lat_deg = math.degrees(lat_si)
                lon_deg = math.degrees(lon_si)
                alt = plat["attrs"].get("altitude", 0.0)
                lines.append(
                    f"[t={t:.3f}] spawn {action.platform} "
                    f"pos={lat_deg:.4f},{lon_deg:.4f} alt={alt:.3f}"
                )
            elif isinstance(action, P.ActivateAction):
                active.add(action.ident)
                on_platform = None
                if action.ident in world.sensors:
                    on_platform = world.sensors[action.ident].get("mount")
                if on_platform:
                    lines.append(f"[t={t:.3f}] activate {action.ident} on {on_platform}")
                else:
                    lines.append(f"[t={t:.3f}] activate {action.ident}")
            elif isinstance(action, P.DeactivateAction):
                active.discard(action.ident)
                lines.append(f"[t={t:.3f}] deactivate {action.ident}")
            elif isinstance(action, P.ReportAction):
                if action.ident not in active:
                    raise PlinthError(
                        "E071", action.line, action.col,
                        f"report on inactive sensor '{action.ident}'; "
                        f"add 'activate {action.ident}' before this report",
                    )
                range_max = 0.0
                if action.ident in world.sensors:
                    range_max = world.sensors[action.ident]["attrs"].get("range_max", 0.0)
                lines.append(
                    f"[t={t:.3f}] report {action.ident} "
                    f"range_max={range_max:.3f} detections=0"
                )
            elif isinstance(action, P.TraceAction):
                lines.append(f'[t={t:.3f}] trace "{action.text}"')
            elif isinstance(action, P.HaltAction):
                if t < duration - 1e-9:
                    raise PlinthError(
                        "E070", action.line, action.col,
                        f"halt at t={t:.3f}s before scenario duration "
                        f"{duration:.3f}s elapses; remove this halt or schedule it "
                        f"at/after t={duration:.3f}",
                    )
                lines.append(f"[t={t:.3f}] halt")
                lines.append(f"[t={t:.3f}] scenario end status=ok")
                return lines
    except PlinthError as e:
        e.partial_trace = lines
        raise

    lines.append(f"[t={duration:.3f}] scenario end status=ok")
    return lines
