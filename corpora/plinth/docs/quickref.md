# PLINTH Quick Reference

A one-page keyword table. See `manual.md` for prose explanation and
`errors.md` for error codes.

## Structural

| Keyword | Use |
|---|---|
| `define` | starts a scenario/platform/sensor/route/signal definition |
| `scenario` | top-level scenario block |
| `platform` | top-level platform block |
| `sensor` | top-level sensor block |
| `route` | top-level route block |
| `signal` | top-level signal block |
| `waypoint` | one stop within a `route` |
| `execute` | top-level timeline block |
| `end_scenario` | closes `scenario` |
| `end_platform` | closes `platform` |
| `end_sensor` | closes `sensor` |
| `end_route` | closes `route` |
| `end_signal` | closes `signal` |
| `end_waypoint` | closes `waypoint` |
| `end_execute` | closes `execute` |
| `type` | introduces the platform/sensor subtype |

## Attributes

| Attribute | Dimension | Blocks |
|---|---|---|
| `angle_mode` | (mode token: `deg`/`rad`) | scenario |
| `epoch` | time | scenario |
| `duration` | time | scenario (required) |
| `step` | time | scenario (required) |
| `tolerance` | bare integer | scenario |
| `label` | string | scenario, platform, sensor, signal |
| `position` | angle pair (`at <lat> <lon>`) | platform (required), waypoint (required) |
| `altitude` | length | platform, waypoint |
| `speed` | speed | platform, waypoint |
| `heading` | angle | platform |
| `pitch` | angle | platform |
| `roll` | angle | platform |
| `mount` | reference (`bind`) | sensor (required) |
| `aperture` | length | sensor |
| `gain` | power | sensor |
| `noise_floor` | power | sensor |
| `range_max` | length | sensor (required) |
| `scan_rate` | frequency | sensor |
| `field_of_view` | bare integer | sensor |
| `frequency` | frequency | signal (required) |
| `bandwidth` | frequency | signal |
| `power` | power | signal |
| `modulation` | string | signal |
| `priority` | bare integer | sensor |

## Statements and actions

| Keyword | Shape |
|---|---|
| `set` | `set <attribute> = <value>` |
| `bind` | `bind <name> <- <identifier>` |
| `at` | spatial in `waypoint`, temporal in `execute` |
| `spawn` | `spawn <platform> [on route <route>]` |
| `on` | part of `spawn ... on route ...` |
| `activate` | `activate <sensor>` |
| `deactivate` | `deactivate <sensor>` |
| `report` | `report <sensor>` |

## Also reserved (cannot be used as identifiers)

`trace`, `halt`, `true`, `false`
