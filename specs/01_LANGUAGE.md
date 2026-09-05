# 01 — PLINTH: the synthetic language, interpreter, and corpus

**Owner: Partner. This is the blocking dependency for the whole project.**
Backend cannot build `verify` and frontend cannot render real output until the
interpreter emits errors. Ship a rough working `parse` command in the first
few hours, then keep hardening while others build against it.

---

## 1. Why a synthetic language

The system's premise is that the model has never seen the language. With
COBOL you can't prove that — there's a decade of Stack Overflow in training
data. With an invented language, **baseline is provably near zero**, so every
point of measured performance is attributable to the tooling rather than
memorization. No other project at the event can make that claim.

You also get the verifier for free, because you write the interpreter.

The known counter-objection is "you built both ends." Mitigations live in
`05_EVAL.md` and `06_DEMO.md`: run COBOL as a second corpus with a compiler we
didn't write, and publish baselines honestly. Build for that.

### Provenance rule — non-negotiable

PLINTH is designed from the **generic public pattern** of nested
simulation-scenario input decks. That pattern is common across many
open tools (OpenFOAM dictionaries, NASTRAN decks, ns-3 configs), and it is
fine to draw on.

Do not derive keyword names, block hierarchies, or semantics from any
proprietary or export-controlled tool anyone on this team has used
professionally. If a name feels familiar, rename it. PLINTH must be
demonstrably our own invention. This costs nothing and removes the question
permanently.

## 2. Design targets

The language must be **hard enough that retrieval matters**:

- 52 keywords — too many to fit comfortably in a prompt preamble, which is
  what forces the tools to earn their place
- Nested blocks with explicit terminators → model must track legal parent/child
- Declaration-before-reference → model must reason about file order
- Mandatory units with dimensional checking → a class of error the model
  cannot bluff past
- Three deliberately counter-intuitive semantics (§5) → punishes
  pattern-matching from other languages
- Two features documented **only in the examples**, absent from the manual
  (§8) → lets us demo discovery from example code

File extension `.plth`. Comments start `#`. Case-sensitive. Whitespace
insignificant except as token separator.

## 3. Lexical grammar

```
IDENT     := [A-Za-z_][A-Za-z0-9_]*
NUMBER    := -?[0-9]+(\.[0-9]+)?          # bare numbers are an ERROR except in count/priority
QUANTITY  := NUMBER UNIT                   # no space permitted: 1500m  not  1500 m
                                           # (deliberate gotcha, see §5.4)
STRING    := "..."                         # no escapes, no newlines
COMMENT   := #.*$
UNIT      := see table below
```

### Units

| Dimension | Units |
|---|---|
| length | `m` `km` `ft` `nmi` |
| time | `s` `min` `hr` |
| speed | `mps` `kts` `kph` |
| angle | `deg` `rad` |
| frequency | `hz` `khz` `mhz` |
| power | `dbw` `w` `kw` |

Canonical internal representation: SI (`m`, `s`, `mps`, `rad`, `hz`, `w`).

## 4. Block grammar

```
program      := toplevel*
toplevel     := scenario | platform | sensor | route | signal | execute

scenario     := "define" "scenario" IDENT NEWLINE scenario_stmt* "end_scenario"
platform     := "define" "platform" IDENT "type" plat_type NEWLINE platform_stmt* "end_platform"
sensor       := "define" "sensor" IDENT "type" sens_type NEWLINE sensor_stmt* "end_sensor"
route        := "define" "route" IDENT NEWLINE waypoint* "end_route"
signal       := "define" "signal" IDENT NEWLINE signal_stmt* "end_signal"
execute      := "execute" NEWLINE exec_stmt* "end_execute"

waypoint     := "waypoint" NEWLINE waypoint_stmt* "end_waypoint"

plat_type    := "air" | "ground" | "surface" | "space"
sens_type    := "radar" | "eo" | "ir" | "esm" | "acoustic"

assign_stmt  := "set" IDENT "=" value
bind_stmt     := "bind" IDENT "<-" IDENT
inherit_stmt := "inherit" "from" IDENT              # EXAMPLES ONLY, see §8

exec_stmt    := time_clause action
time_clause  := "at" QUANTITY:time
              | "every" QUANTITY:time [ "for" QUANTITY:time ]   # EXAMPLES ONLY, §8
action       := "spawn" IDENT [ "on" "route" IDENT ]
              | "activate" IDENT
              | "deactivate" IDENT
              | "report" IDENT
              | "trace" STRING
              | "halt"
```

### Full keyword list (52)

Structural (16): `define` `scenario` `platform` `sensor` `route` `signal`
`waypoint` `execute` `end_scenario` `end_platform` `end_sensor` `end_route`
`end_signal` `end_waypoint` `end_execute` `type`

Attributes (24): `angle_mode` `epoch` `duration` `step` `tolerance` `label`
`position` `altitude` `speed` `heading` `pitch` `roll` `mount` `aperture`
`gain` `noise_floor` `range_max` `scan_rate` `field_of_view` `frequency`
`bandwidth` `power` `modulation` `priority`

Statements/actions (12): `set` `bind` `inherit` `from` `at` `every` `for`
`spawn` `on` `activate` `deactivate` `report`

Also reserved: `trace` `halt` `true` `false`

Attribute legality by block — the interpreter enforces this and it is the
main thing `lookup_symbol` serves:

| Block | Required | Optional |
|---|---|---|
| `scenario` | `duration` `step` | `angle_mode` `epoch` `label` `tolerance` |
| `platform` | `position` | `altitude` `speed` `heading` `pitch` `roll` `label` |
| `sensor` | `mount` `range_max` | `aperture` `gain` `noise_floor` `scan_rate` `field_of_view` `priority` `label` |
| `waypoint` | `position` | `altitude` `speed` |
| `signal` | `frequency` | `bandwidth` `power` `modulation` `label` |

`angle_mode` defaults to `deg` if omitted.

## 5. The four gotchas

These exist to defeat pattern-matching from familiar languages. Each has a
dedicated error code and at least three eval cases.

### 5.1 `set` vs `bind` — assignment vs deferred reference

`set` assigns a value immediately. `bind` creates a reference resolved at end
of parse, so it may point forward.

```
define platform uav_02 type air
  set altitude = 2200m           # value, immediate
  bind primary_sensor <- radar_b # reference, radar_b may be defined later
end_platform
```

- `bind x <- 5m` → **E021** (bind target must be an identifier)
- `set primary_sensor = radar_b` → **E022** (use bind for references)
- `bind` target never defined anywhere → **E020** (unresolved bind)

This is the single most productive gotcha. A model will reach for `set`
universally. Rich source of repair-loop material.

### 5.2 `at` is context-sensitive

Inside `waypoint`: spatial. Inside `execute`: temporal.

```
waypoint
  position at 45.20deg -100.10deg     # spatial
end_waypoint

execute
  at 30s activate radar_a             # temporal
end_execute
```

- Spatial form inside `execute` → **E030**
- Temporal form inside `waypoint` → **E031**

### 5.3 `angle_mode` must match every angle literal

If `scenario` declares `angle_mode rad`, every angle quantity in the file must
use `rad`. Mixing → **E042**. This is a whole-file consistency constraint, not
a local one, which is exactly the kind of thing models miss.

### 5.4 No space between number and unit

`1500m` is valid. `1500 m` is **E043**. Bare `1500` in a dimensioned field is
**E040**.

Exception: `count`, `priority`, `field_of_view` multiplier and `step`
subdivision take bare integers. (`step` still takes a time quantity — the
subdivision case is `tolerance`.)

Keep this one. It is cheap to fix once known and generates immediate
first-iteration failures that the repair loop resolves visibly — good demo
material, and it is the sort of thing every real legacy language has.

## 6. Error codes

The interpreter must emit these exactly. They key the failure-memory system
and the eval report.

| Code | Meaning |
|---|---|
| E001 | Unexpected token |
| E002 | Unterminated block (missing `end_*`) |
| E003 | Unknown keyword |
| E004 | Mismatched terminator (`end_sensor` closing a `platform`) |
| E010 | Duplicate definition |
| E011 | Reference to undefined identifier |
| E012 | Forward reference not permitted here (use `bind`) |
| E020 | Unresolved bind at end of parse |
| E021 | Bind target must be an identifier |
| E022 | `set` used on a reference; use `bind` |
| E030 | Spatial `at` outside waypoint context |
| E031 | Temporal `at` outside execute context |
| E040 | Missing unit on numeric literal |
| E041 | Dimensional mismatch for field |
| E042 | Angle unit conflicts with scenario `angle_mode` |
| E043 | Space between number and unit |
| E050 | Unknown attribute for this block type |
| E051 | Attribute not permitted in this block |
| E052 | Required attribute missing |
| E060 | Value out of permitted range |
| E070 | Runtime: `halt` before scenario duration elapsed |
| E071 | Runtime: `report` on inactive sensor |
| E072 | Runtime: `spawn` of already-spawned platform |

Message format is human-readable and **must name the fix** where possible:

```
candidate.plth:14:9: E022: 'set' used on reference 'primary_sensor'; use 'bind primary_sensor <- ...'
```

Error messages that name the fix dramatically improve repair-loop convergence.
Treat message quality as a first-class feature, not polish.

## 7. Interpreter implementation

Python 3.11+, stdlib only. Target ~500 lines. Package at `languages/plinth/`.

```
languages/plinth/plinth/
  __init__.py
  lexer.py       # ~90 lines
  parser.py      # recursive descent → AST, ~180 lines
  checker.py     # symbol resolution, units, attribute legality, ~140 lines
  runtime.py     # deterministic tick execution, ~90 lines
  symbols.py     # emits the grammar as JSON (see below)
  cli.py         # argparse entrypoint
```

### CLI — this is the contract the sandbox calls

```
plinth parse [--json] FILE     # exit 0 clean, 1 if errors
plinth run   [--json] FILE     # parse then execute; trace to stdout
plinth symbols --json          # dump built-in grammar as ground truth
```

`--json` output for `parse` and `run` matches the verifier result contract in
`00_ARCHITECTURE.md` §5 exactly. Verify against that doc before shipping.

### `plinth symbols --json` — do not skip this

This is the analog of walking a real tool's C++ `ProcessInput` methods to
recover its true grammar. It makes the symbol table **ground truth rather than
doc-derived**, and it is a genuinely novel part of the pitch.

```json
{
  "language": "plinth",
  "symbols": [
    {
      "name": "altitude",
      "kind": "attribute",
      "valid_parents": ["platform", "waypoint"],
      "arg_shape": "<quantity:length>",
      "dimension": "length",
      "required": false,
      "range": [0, 30000]
    },
    {
      "name": "bind",
      "kind": "statement",
      "valid_parents": ["platform", "sensor"],
      "arg_shape": "IDENT <- IDENT"
    }
  ]
}
```

Emit **all 52 keywords**. Derive the table from the same constants the checker
uses — never maintain it separately, or it will drift.

### Runtime trace format

Deterministic, diffable, no timestamps from the wall clock. This is what
`pairs/` compares against.

```
[t=0.000] scenario coastal_watch start step=0.500 duration=60.000
[t=5.000] spawn uav_01 pos=45.2000,-100.1000 alt=1500.000
[t=5.000] activate radar_a on uav_01
[t=10.000] report radar_a range_max=80000.000 detections=0
[t=60.000] scenario end status=ok
```

Fixed 3-decimal formatting throughout. No trailing whitespace. Newline at EOF.

## 8. The examples-only features

Two features appear **only in `examples/`**, never in `docs/manual.md`. This
is the realistic condition — real legacy docs are always incomplete — and it
gives us the best single moment in the demo: the agent discovering a
capability from example code that no documentation describes.

1. **`inherit from <platform>`** — copies all attributes from a previously
   defined platform, which the current block may then override. Appears in
   `patrol_pair.plth` and `layered_ir.plth`.
2. **`every <t> for <t>`** — repeat modifier in `execute`. Appears in
   `sweep_test.plth` and `endurance.plth`.

`plinth symbols` **does** report both, since it reflects real grammar. That's
the intended asymmetry: docs are incomplete, the toolchain is not. It
demonstrates precisely why deriving the symbol table from the toolchain beats
scraping the manual.

Do not mention these in the manual. If someone "fixes" that, revert it.

## 9. Corpus authoring

```
corpora/plinth/
  meta.yaml
  docs/
    manual.md          # ~1200 lines, covers ~70% of keywords
    quickref.md         # keyword table, deliberately missing §8 features
    errors.md           # E001–E052 only. Runtime codes E070+ omitted.
  examples/            # 15 programs, all parse-clean
  pairs/
    001/task.txt  001/expected.txt  001/solution.plth
    ...
```

### Deliberate documentation gaps

Realistic incompleteness, not random sabotage:

- `inherit`, `every ... for` — absent entirely (§8)
- `signal` block — mentioned in a table, never explained
- `tolerance`, `scan_rate`, `modulation` — listed without semantics
- Runtime errors E070–E072 — undocumented
- The `angle_mode` whole-file constraint (§5.3) — stated once, in a footnote
- The no-space rule (§5.4) — never stated, only visible in examples

Everything a model needs to succeed is somewhere in the corpus. Some of it is
only in the examples. That is the point.

### The 15 examples

Each must parse clean, run clean, and have a header comment naming what it
demonstrates. Coverage targets:

| File | Demonstrates |
|---|---|
| `minimal.plth` | smallest valid scenario |
| `coastal.plth` | single air platform + radar |
| `patrol_pair.plth` | **`inherit from`** |
| `layered_ir.plth` | **`inherit`** + multiple sensor types |
| `sweep_test.plth` | **`every ... for`** |
| `endurance.plth` | **`every ... for`** + long duration |
| `route_long.plth` | multi-waypoint route |
| `radians.plth` | `angle_mode rad` throughout |
| `bind_forward.plth` | `bind` to a later definition |
| `bind_chain.plth` | multiple binds across blocks |
| `emitter.plth` | `signal` block (undocumented semantics) |
| `ground_net.plth` | ground + surface platforms |
| `multi_sensor.plth` | 4 sensors on one platform, `priority` |
| `space_track.plth` | space platform, large ranges |
| `full_scenario.plth` | ~120 lines, everything combined |

### The pairs

15 `(task, expected_output)` triples. `task.txt` is natural language, phrased
as a user would. `expected.txt` is exact interpreter trace output.
`solution.plth` is a known-good answer, used only for grading, never exposed
via MCP tools.

**Do not let solutions leak into the retrieval index.** `ingest` must skip
`pairs/*/solution.plth`. Add a test for this.

## 10. Definition of done

- [ ] `plinth parse` on all 15 examples → exit 0
- [ ] `plinth run` on all 15 → matches a committed golden trace
- [ ] `plinth symbols --json` → 52 symbols, validates against §7 schema
- [ ] Every error code E001–E072 reachable, each with a fixture in
      `languages/plinth/tests/fixtures/`
- [ ] Error messages name the fix where a fix is nameable
- [ ] `docs/manual.md` written, gaps per §9 verified present
- [ ] 15 pairs complete, solutions excluded from ingest
- [ ] Dockerfile → `ashlar/plinth:latest`, runs with `--network=none`
- [ ] `grep -ri "<any proprietary tool name>" .` → clean (§1 provenance rule)
