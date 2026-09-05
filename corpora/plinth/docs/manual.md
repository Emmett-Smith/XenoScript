# PLINTH Language Manual

PLINTH is a scenario input-deck language for describing simulation
scenarios: platforms moving around, sensors detecting things, signals
being emitted, and a timeline of actions to execute. Files use the
extension `.plth`. Comments start with `#` and run to end of line. PLINTH
is case-sensitive.

This manual covers the core of the language: scenarios, platforms,
sensors, routes, and the execute timeline. It does not claim to be
exhaustive -- some blocks and fields are only briefly listed in the
quick-reference table (`quickref.md`) without full explanation here.
Consult the `examples/` directory in the corpus for working programs;
some capabilities are demonstrated there before they are written up here.

## 1. File structure

A PLINTH file is a sequence of top-level definitions:

```
define scenario <name>
  ...
end_scenario

define platform <name> type <air|ground|surface|space>
  ...
end_platform

define sensor <name> type <radar|eo|ir|esm|acoustic>
  ...
end_sensor

define route <name>
  waypoint
    ...
  end_waypoint
end_route

execute
  ...
end_execute
```

Every block that opens with `define <kind> <name>` must be closed with the
matching `end_<kind>`. Closing a block with the wrong terminator (for
example, `end_sensor` where `end_platform` was expected) is an error.
Names are ordinary identifiers: a letter or underscore followed by
letters, digits, or underscores.

Definitions generally must appear before they are referenced elsewhere in
the file. If you reference a platform, sensor, or route before its
`define` block, the checker will reject it -- reorder your file so
producers come before consumers.

## 2. Numbers, quantities, and units

A bare number by itself (like `5` or `-3.2`) is only accepted for a
handful of fields that take a plain count rather than a measured
quantity (see `priority` and `field_of_view` below). Everywhere else, a
numeric literal must be paired with a unit to form a *quantity*, for
example `1500m` or `40mps`.

Units are grouped by dimension:

| Dimension | Units |
|---|---|
| length | `m` `km` `ft` `nmi` |
| time | `s` `min` `hr` |
| speed | `mps` `kts` `kph` |
| angle | `deg` `rad` |
| frequency | `hz` `khz` `mhz` |
| power | `dbw` `w` `kw` |

Internally, all quantities are converted to a canonical SI representation
(`m`, `s`, `mps`, `rad`, `hz`, `w`) so that mixed units compare correctly.
You may write quantities in whichever unit is convenient; the checker
handles the conversion.

Every field expects a specific dimension. Writing a length where a time
is expected (or vice versa) is a dimensional mismatch and will be
rejected, regardless of whether you remembered to attach a unit.

## 3. The `scenario` block

Every file needs exactly one `scenario` block naming the overall run:

```
define scenario coastal_watch
  set duration = 60s
  set step = 0.5s
end_scenario
```

`duration` and `step` are required and both take a time quantity.
`duration` is the total length of the simulated run; `step` is how finely
the runtime advances the simulation clock.

Optional scenario fields: `epoch`, `label`, `tolerance`, and `angle_mode`.
`epoch` takes a time quantity (an offset for the scenario's start time).
`label` takes a free-form string, useful for annotating a run:

```
set label = "baseline run, no jamming"
```

`tolerance` is described in the quick-reference table; this manual does
not cover its intended use in detail.

> Note: `angle_mode` (see the units table above) selects whether angle
> quantities in this file are written in `deg` or `rad`. Once declared,
> every angle-dimensioned value in the *entire file* must use that same
> unit -- mixing `deg` and `rad` quantities in one file is rejected. If
> `angle_mode` is omitted, `deg` is assumed.

## 4. The `platform` block

A platform is a moving (or stationary) entity: an aircraft, a ground
station, a ship, a satellite.

```
define platform uav_01 type air
  position at 45.20deg -100.10deg
  set altitude = 1500m
  set speed = 40mps
end_platform
```

The `type` keyword is required and must be one of `air`, `ground`,
`surface`, or `space`.

`position` is required for every platform. Unlike other fields, it is
not assigned with `set` -- it uses its own `at` form giving latitude and
longitude as angle quantities: `position at <lat> <lon>`.

Optional platform fields, all assigned with `set`: `altitude` (length),
`speed` (speed), `heading` (angle), `pitch` (angle), `roll` (angle), and
`label` (string).

```
define platform uav_02 type ground
  position at 33.90deg -118.20deg
  set altitude = 10m
  set heading = 270deg
end_platform
```

### Linking a platform to something else

Sometimes a platform needs to reference another identifier rather than
hold a value -- for example, "this platform's primary sensor is
`radar_b`". Values (numbers, quantities, strings) are assigned with
`set`. References to other named things are assigned with `bind`:

```
define platform uav_02 type air
  position at 45.20deg -100.10deg
  bind primary_sensor <- radar_b
end_platform
```

`bind` creates a named reference that is resolved once the whole file has
been read, so the sensor it points to may be defined later in the file --
unlike ordinary references, which must already be defined at the point
they're used. If you try to `set` a field to what looks like another
identifier's name, the checker will tell you to use `bind` instead.

## 5. The `sensor` block

A sensor is attached to a platform and detects things.

```
define sensor radar_a type radar
  bind mount <- uav_01
  set range_max = 80000m
end_sensor
```

`type` is required and must be one of `radar`, `eo`, `ir`, `esm`, or
`acoustic`.

`mount` and `range_max` are required. `range_max` is an ordinary length
quantity assigned with `set`. `mount` identifies which platform the
sensor is physically mounted on -- since this is a reference to another
definition rather than a value, it is assigned with `bind`, exactly like
the `primary_sensor` example above:

```
bind mount <- uav_01
```

Optional sensor fields: `aperture` (length), `gain` (power),
`noise_floor` (power), `priority` (a bare integer, no unit -- see below),
and `label` (string). `scan_rate` and `field_of_view` are listed in the
quick-reference table but not covered further here.

### Bare-integer fields

Most numeric fields require a unit. `priority` is an exception: it takes
a plain integer with no unit attached, used to rank sensors relative to
each other when a platform carries more than one:

```
set priority = 1
```

## 6. Routes and waypoints

A `route` is a named sequence of waypoints that a platform can be spawned
onto:

```
define route coastal_leg
  waypoint
    position at 1.00deg 1.00deg
    set altitude = 1200m
  end_waypoint
  waypoint
    position at 2.00deg 2.00deg
    set altitude = 1400m
    set speed = 55mps
  end_waypoint
end_route
```

Each `waypoint` requires a `position` (using the same `position at <lat>
<lon>` form as platforms) and optionally `altitude` and `speed`.

## 7. The `execute` block

`execute` describes what happens, and when, during the run. It contains a
list of timed actions:

```
execute
  at 5s spawn uav_01
  at 5s activate radar_a
  at 10s report radar_a
end_execute
```

Each line pairs a time clause with an action. The only time clause
covered in this manual is `at <time>`, which fires the action once, at
that simulated time.

### `at` means different things in different places

Inside a `waypoint`, `at` follows `position` and takes two angle
quantities (latitude and longitude) -- it is spatial. Inside `execute`,
`at` takes a single time quantity and precedes an action -- it is
temporal. Using the wrong shape in the wrong place (for example, a
spatial `position at <lat> <lon>` line inside an `execute` block) is
rejected.

### Actions

- `spawn <platform>` -- brings a platform into the simulation.
  Optionally, `spawn <platform> on route <route>` also assigns it a
  route to follow.
- `activate <sensor>` -- turns a sensor on.
- `deactivate <sensor>` -- turns a sensor off.
- `report <sensor>` -- has an active sensor produce a report in the
  trace. Reporting an inactive sensor is an error.
- `trace "<text>"` -- emits an arbitrary string into the trace, useful
  for annotating what's happening at a given time.
- `halt` -- stops the run.

```
execute
  at 1s spawn uav_01
  at 2s activate radar_a
  at 30s report radar_a
  at 31s trace "midpoint check complete"
end_execute
```

## 8. The `signal` block

| Block | Required | Optional |
|---|---|---|
| `signal` | `frequency` | `bandwidth`, `power`, `modulation`, `label` |

See the quick-reference table for the full field list. This manual does
not walk through `signal` block semantics in prose.

## 9. Running a scenario

```
plinth parse myfile.plth
plinth run myfile.plth
```

`parse` checks the file without executing it. `run` parses and then
simulates the scenario, printing a trace line for every event. See
`errors.md` for the list of error codes the checker can report.
