# COBOL Language Manual (GnuCOBOL, free-form source)

This manual covers the subset of COBOL exercised by this corpus's
`examples/` and `pairs/`: program structure, `DISPLAY`, `WORKING-STORAGE`
variables and `PIC` clauses, `MOVE`, arithmetic (`COMPUTE`, `ADD`,
`SUBTRACT`), conditionals (`IF` / `ELSE`), and loops (`PERFORM`). COBOL is
a real, decades-old language standardized by ANSI/ISO; this is not an
exhaustive reference for the full standard, only for what you need to
write and read the programs in this corpus. Consult `examples/` for
working programs -- every one of them compiles cleanly with the real
`cobc` compiler (GnuCOBOL 3.2).

All source in this corpus is **free-form** (compiled with `cobc -free`),
not the historical fixed-column format. Free-form COBOL does not use the
old column 1-6/7/8-11/12-72 layout; statements can start at any column,
and lines can be as long as you like. The two formats are otherwise the
same language.

## 1. Comments

Free-form COBOL comments start with `*>` and run to the end of the line.
They can be a whole line by themselves or trail after code on the same
line:

```cobol
*> this is a whole-line comment
DISPLAY "HELLO" *> this is a trailing comment
```

(Fixed-form COBOL instead uses a `*` in column 7 of an otherwise-empty
line; that convention does not apply to `-free` source and is not used
anywhere in this corpus.)

## 2. Program structure: the four divisions

Every COBOL program is organized into divisions, in this fixed order.
Not all are required for a given program, but the ones present must
appear in this order:

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. program-name.

ENVIRONMENT DIVISION.
    ... (rarely needed for this corpus's programs)

DATA DIVISION.
WORKING-STORAGE SECTION.
    ... (variable declarations go here)

PROCEDURE DIVISION.
    ... (executable statements go here)
    STOP RUN.
```

- `IDENTIFICATION DIVISION.` and `PROGRAM-ID. name.` are mandatory in
  every program in this corpus. The program name is a COBOL identifier
  (letters, digits, hyphens); by convention this corpus uses
  upper-case names matching the file's purpose.
- `DATA DIVISION.` with a `WORKING-STORAGE SECTION.` is only needed if the
  program declares variables. A program that only `DISPLAY`s literals
  needs no `DATA DIVISION` at all (see `examples/hello.cbl`).
- `PROCEDURE DIVISION.` holds the executable statements and is mandatory.
- `STOP RUN.` ends execution. Every program in this corpus ends with it.
- Every clause and statement in COBOL ends with a period (`.`). This is
  easy to forget and produces confusing compiler errors when missing --
  GnuCOBOL will often report the error on the *next* line, not the one
  that's actually missing the period.

## 3. `DISPLAY` -- writing output

`DISPLAY` prints one or more items to standard output, each item
separated by nothing unless you add literal spaces, followed by a
newline:

```cobol
DISPLAY "HELLO, WORLD.".
```

Multiple items in one `DISPLAY` are concatenated on one line with no
automatic separator -- you must supply spaces yourself inside the
literals, or use multiple string literals with explicit padding:

```cobol
DISPLAY "TOTAL: " TOTAL-AMOUNT.
```

This prints the literal `TOTAL: ` immediately followed by the current
value of the variable `TOTAL-AMOUNT`, with no extra space unless the
literal itself ends in one.

String literals are delimited with double quotes (`"..."`) in this
corpus (single quotes also work in GnuCOBOL by default, but this corpus
always uses double quotes for consistency).

## 4. `WORKING-STORAGE SECTION` and `PIC` clauses

Variables (called "data items" in COBOL) are declared in
`WORKING-STORAGE SECTION`, each with a level number, a name, and a
`PIC` (picture) clause describing its type and size:

```cobol
DATA DIVISION.
WORKING-STORAGE SECTION.
01  CUSTOMER-NAME    PIC X(20).
01  ITEM-COUNT       PIC 9(4).
01  UNIT-PRICE       PIC 9(4)V99.
01  IS-VALID         PIC X VALUE "Y".
```

- The level number `01` marks a top-level, independent item. (Level
  numbers `02`-`49` build hierarchical records; this corpus's examples
  stick to flat `01` items, which is all that's needed for the programs
  here.)
- `PIC X(n)` declares an alphanumeric field of `n` characters.
  `PIC X` alone is a single character.
- `PIC 9(n)` declares an unsigned numeric field of `n` digits, no
  decimal point.
- `PIC 9(n)V9(m)` declares a numeric field with `n` digits before an
  *implied* decimal point and `m` digits after it. The `V` is not
  stored or displayed -- it just tells COBOL where the decimal point
  belongs when the value is used in arithmetic. `PIC 9(4)V99` holds
  values from `0000.00` to `9999.99` conceptually, displayed as the
  digits only (`000000` for zero) unless you format it for display.
- `PIC S9(n)` adds a sign (`S`) so the field can hold negative values.
- `VALUE` gives a data item its initial value at program start. Without
  it, numeric fields typically start at zero and alphanumeric fields at
  spaces, but relying on that is sloppy style -- prefer an explicit
  `VALUE` clause, which this corpus's examples always do for anything
  read before being written.

## 5. `MOVE` -- assignment

`MOVE` copies a value into a data item. It does not evaluate
expressions -- for arithmetic, use `COMPUTE`, `ADD`, or `SUBTRACT`
(section 6).

```cobol
MOVE "SMITH" TO CUSTOMER-NAME.
MOVE 42 TO ITEM-COUNT.
MOVE ITEM-COUNT TO BACKUP-COUNT.
```

`MOVE` truncates or pads to fit the destination's `PIC` clause: moving a
longer string into a shorter `PIC X(n)` field truncates on the right;
moving a shorter one pads with trailing spaces. Moving a number into a
field with fewer digits truncates the high-order (left) digits, which is
a common source of silent bugs -- size destination fields generously.

## 6. Arithmetic: `COMPUTE`, `ADD`, `SUBTRACT`

`COMPUTE` evaluates a normal arithmetic expression and stores the result:

```cobol
COMPUTE TOTAL-PRICE = UNIT-PRICE * QUANTITY.
COMPUTE AVERAGE = (SCORE-1 + SCORE-2 + SCORE-3) / 3.
```

Operators are `+`, `-`, `*`, `/`, and `**` (exponentiation), with normal
precedence and parentheses. `COMPUTE` is the preferred way to do any
arithmetic more complex than a single add or subtract.

`ADD` and `SUBTRACT` are shorter forms for the simple cases:

```cobol
ADD 1 TO ITEM-COUNT.
ADD PRICE-A PRICE-B GIVING TOTAL-PRICE.
SUBTRACT DISCOUNT FROM TOTAL-PRICE.
SUBTRACT 1 FROM ITEM-COUNT GIVING REMAINING-COUNT.
```

- `ADD a TO b` adds `a` into `b`, storing the result back in `b`.
- `ADD a b GIVING c` adds `a` and `b`, storing the result in `c` (leaves
  `a` and `b` unchanged).
- `SUBTRACT a FROM b` subtracts `a` from `b`, storing the result back in
  `b`.
- `SUBTRACT a FROM b GIVING c` subtracts `a` from `b`, storing the
  result in `c`.

## 7. Conditionals: `IF` / `ELSE`

```cobol
IF ITEM-COUNT > 100
    DISPLAY "BULK ORDER"
ELSE
    DISPLAY "STANDARD ORDER"
END-IF.
```

- Comparison operators: `>`, `<`, `=`, `>=`, `<=`, `NOT =` (or `<>` in
  GnuCOBOL). Word forms `GREATER THAN`, `LESS THAN`, `EQUAL TO` also
  work and are common in older COBOL, but this corpus uses the symbolic
  forms for brevity.
- `END-IF` is the modern, explicit scope terminator. It's not strictly
  required if the `IF` is the last thing before a period, but using it
  is clearer and this corpus's examples always include it.
- `ELSE` is optional; an `IF` with no `ELSE` simply does nothing when the
  condition is false.
- Compound conditions use `AND` / `OR`:

  ```cobol
  IF ITEM-COUNT > 0 AND ITEM-COUNT < 10
      DISPLAY "SMALL ORDER"
  END-IF.
  ```

## 8. Loops: `PERFORM`

COBOL has no `for`/`while` keyword; all looping is done with `PERFORM`,
in three shapes used in this corpus:

### 8.1 Counted loop: `PERFORM ... TIMES`

```cobol
PERFORM 5 TIMES
    DISPLAY "HELLO"
END-PERFORM.
```

Runs the body a fixed number of times. If you need a loop counter
inside the body, use the `VARYING` form instead (below), or maintain
your own counter variable with `ADD`.

### 8.2 Counted loop with an index: `PERFORM VARYING`

```cobol
PERFORM VARYING WS-INDEX FROM 1 BY 1 UNTIL WS-INDEX > 5
    DISPLAY "COUNT IS " WS-INDEX
END-PERFORM.
```

`WS-INDEX` must be a numeric `WORKING-STORAGE` data item declared ahead
of time. It starts at `1`, increases by `1` each iteration, and the loop
stops once the `UNTIL` condition becomes true -- note the condition is
checked *before* each iteration (including the first), so the body never
runs once `WS-INDEX > 5` is already true at the start.

### 8.3 Condition-controlled loop: `PERFORM ... UNTIL`

```cobol
MOVE 1 TO WS-INDEX.
PERFORM UNTIL WS-INDEX > 5
    DISPLAY "COUNT IS " WS-INDEX
    ADD 1 TO WS-INDEX
END-PERFORM.
```

Equivalent to a `while` loop: the condition is checked before each
iteration, and you're responsible for incrementing the controlling
variable yourself inside the body (forgetting to do so is the classic
infinite-loop bug in COBOL, same as any other language's `while`).

### 8.4 Named paragraphs and `PERFORM paragraph-name`

Code can also be factored into named paragraphs in `PROCEDURE DIVISION`
and invoked with `PERFORM`:

```cobol
PROCEDURE DIVISION.
MAIN-LOGIC.
    DISPLAY "STARTING".
    PERFORM PRINT-GREETING.
    DISPLAY "DONE".
    STOP RUN.

PRINT-GREETING.
    DISPLAY "HELLO FROM A PARAGRAPH".
```

A paragraph name is any COBOL identifier followed by a period, on its
own line, before the statements that belong to it. `PERFORM
PRINT-GREETING` runs every statement in that paragraph once, then
returns control to the line after the `PERFORM`. This is COBOL's
equivalent of calling a subroutine within the same program. `PERFORM
paragraph-name TIMES` and `PERFORM paragraph-name UNTIL condition` also
work, running the named paragraph repeatedly instead of an inline block.

## 9. Putting it together

A program combining several of the above -- declare data, read no
input (this corpus's examples are all self-contained, no `ACCEPT` from a
terminal), compute something, branch on it, and loop -- looks like:

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. GRADEBOOK.

DATA DIVISION.
WORKING-STORAGE SECTION.
01  WS-SCORE       PIC 9(3) VALUE 0.
01  WS-INDEX       PIC 9(2) VALUE 1.
01  WS-TOTAL       PIC 9(5) VALUE 0.
01  WS-AVERAGE     PIC 9(3) VALUE 0.

PROCEDURE DIVISION.
    PERFORM VARYING WS-INDEX FROM 1 BY 1 UNTIL WS-INDEX > 3
        COMPUTE WS-SCORE = WS-INDEX * 10
        ADD WS-SCORE TO WS-TOTAL
    END-PERFORM.
    COMPUTE WS-AVERAGE = WS-TOTAL / 3.
    IF WS-AVERAGE > 15
        DISPLAY "AVERAGE ABOVE THRESHOLD: " WS-AVERAGE
    ELSE
        DISPLAY "AVERAGE AT OR BELOW THRESHOLD: " WS-AVERAGE
    END-IF.
    STOP RUN.
```

See `examples/combined.cbl` for a compiled, verified version of a program
in this same shape.

## 10. Common `cobc` errors you'll actually see

`cobc` (GnuCOBOL) prints plain-text diagnostics, not JSON, one per line,
in the shape `file:line: severity: message` where `severity` is
`error`, `warning`, or `note`. A few you're likely to hit while writing
programs for this corpus:

- Missing period at the end of a division header or statement: often
  surfaces as a confusing syntax error on the *following* line, because
  the compiler kept reading the next statement as part of the previous
  one.
- Referencing a data item that was never declared in `WORKING-STORAGE`:
  `error: 'FOO' is not defined`.
- Mismatched `PIC` size in `MOVE` or `COMPUTE` is usually **not** a
  compile error -- COBOL truncates or pads silently at run time. Check
  output values, not just compiler exit status, when a program compiles
  but produces a wrong-looking number.
- Leaving off `END-IF` or `END-PERFORM` when the block isn't naturally
  terminated by the following period placement can attach later
  statements to the wrong scope; GnuCOBOL will sometimes accept this
  and sometimes flag it, so always terminate blocks explicitly in new
  code.
