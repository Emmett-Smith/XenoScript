# PLINTH Error Codes

`plinth parse` and `plinth run` report errors with a code, a line and
column, and a message that names the fix where one is nameable. This
page documents the codes you're most likely to run into while writing a
file. (Codes in the 070+ range, raised only while a scenario is actually
executing, aren't covered on this page.)

## Structural (E001-E004)

- **E001** -- unexpected token. Something appears where the grammar
  didn't expect it: a misplaced keyword, a missing value, or a statement
  that doesn't belong in the current block.
- **E002** -- unterminated block. A block was opened (`define platform
  ...`, `execute`, ...) but the file ended, or another top-level
  definition started, before the matching `end_*` was found.
- **E003** -- unknown keyword. Used for enum-like slots that only accept
  a fixed set of words -- for example, `type` on a platform must be one
  of `air`, `ground`, `surface`, `space`, and `angle_mode` must be `deg`
  or `rad`.
- **E004** -- mismatched terminator. The block was closed with the wrong
  `end_*` keyword, e.g. `end_sensor` closing a `platform`.

## Identifiers (E010-E012)

- **E010** -- duplicate definition. Either two top-level blocks share a
  name, or the same attribute was set twice on the same block.
- **E011** -- reference to an undefined identifier.
- **E012** -- forward reference not permitted here. Ordinary references
  (unlike `bind`) must point to something already defined earlier in the
  file. Move the definition earlier, or use `bind` if you specifically
  need a deferred reference.

## `set` vs `bind` (E020-E022)

- **E020** -- unresolved bind. A `bind ... <- target` was never resolved
  because `target` isn't defined anywhere in the file.
- **E021** -- bind target must be an identifier. `bind x <- 5m` is
  invalid; the right-hand side of `<-` must name another definition.
- **E022** -- `set` used on a reference. If the value you're assigning
  is really the name of another definition, use `bind` instead of `set`.

## Context-sensitive `at` (E030-E031)

- **E030** -- spatial `at` outside its valid context. A `position at
  <lat> <lon>` line was found somewhere that only takes temporal `at`
  (such as inside `execute`).
- **E031** -- temporal `at` outside its valid context. An `at <time>
  <action>` line was found somewhere that expects the spatial form
  (such as inside `waypoint`).

## Units and dimensions (E040-E043)

- **E040** -- missing unit on a numeric literal. The field expects a
  quantity (a number with a unit attached); a bare number was given
  instead.
- **E041** -- dimensional mismatch. The unit attached to the value
  doesn't match the dimension the field expects (for example, a length
  where a speed was expected).
- **E042** -- angle unit conflicts with the scenario's `angle_mode`.
- **E043** -- space between a number and its unit. Quantities are
  written with no space, e.g. `1500m`.

## Attribute legality (E050-E052)

- **E050** -- unknown attribute for this block type. The name given
  isn't a recognized attribute at all.
- **E051** -- attribute not permitted in this block. The name is a real
  attribute, just not a legal one for the block it was used in.
- **E052** -- required attribute missing. A block finished without
  setting one of its required fields.

## Value ranges (E060)

- **E060** -- value out of permitted range for its field.
