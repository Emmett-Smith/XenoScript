# MUMPS / M Language Reference (XenoScript corpus)

This corpus targets [Reference Standard M](https://github.com/Reference-Standard-M/rsm)
(RSM), a real, open-source implementation of ANSI/MDC Standard M X11.1-1995
(ISO/IEC 11756:1999), built and run natively on this machine. Every construct
below has been executed for real against the real `rsm` interpreter, not
transcribed from memory.

## Execution model for this corpus (important, read first)

Programs in this corpus are **direct-mode scripts**: a sequence of top-level
M command lines, fed to `rsm` on its standard input and executed one line at
a time, top to bottom, in a single shared local-variable scope for the whole
run -- like a shell script, not a compiled multi-entry-point M *routine*.

Two real consequences of this:

- `DO <label>` / `GOTO <label>` to a line label **do not work** here --
  labels are a feature of compiled routines stored in `^$ROUTINE`, which this
  corpus's execution path does not use. Write straight-line code: `FOR`,
  `IF`/`ELSE`, and full expressions cover everything a task in this corpus
  needs.
- `READ` is not usable here either -- standard input is the program's own
  source text, not a separate interactive channel. Don't use it.
- Multi-line dotted-DO blocks (`DO` followed by lines indented with a
  leading `.`) **do not work** either, for the same reason as labels --
  verified live: a dotted-DO block fed this way produces `M13 Invalid
  line reference`. Keep a `FOR`/`IF` loop body entirely on its own
  single line instead (see the `FOR` section below).

## Globals (`^name`) -- persistent, and wiped clean before every check

A name starting with `^` is a *global* -- M's built-in, disk-backed
database (this is the feature that made M the dominant EHR language:
VistA, Epic, and Meditech are all built on it). Unlike local variables,
globals in this corpus persist in one shared environment across
different runs, so this corpus wipes every global back to empty before
each check -- a program can freely set and read its own globals within
one run, but should never depend on a global that some *other*, earlier
task might have left behind.

```m
SET ^PATIENT(1)="DOE,JANE^34^F"
WRITE $PIECE(^PATIENT(1),"^",1),!   ; DOE,JANE

; Iterating every record in a global array, oldest pattern in M:
SET IDX=""
FOR  SET IDX=$ORDER(^PATIENT(IDX)) QUIT:IDX=""  WRITE IDX,": ",^PATIENT(IDX),!
```

## Comments

A semicolon starts a comment, either as a whole line or after at least one
space following a command:

```m
; this whole line is a comment
WRITE "hi",!  ; trailing comment after a command
```

## Output: WRITE

`WRITE` prints one or more comma-separated arguments. `!` is the "new line"
write argument (not a literal `!` character):

```m
WRITE "hello",!
WRITE 1+2,!
```

## Variables: SET, NEW

`SET` assigns a local variable. Local variables need no declaration and
persist for the rest of the run once set:

```m
SET X=10
SET Y=X*2
WRITE Y,!
```

`NEW` gives a variable a fresh, empty value, saving and restoring any outer
value when the enclosing block ends (matters most inside `FOR`/`DO` blocks;
for straight-line scripts in this corpus it mainly documents intent).

## Arithmetic and comparison operators

Verified live, in this exact form (no spaces around operators, M is
whitespace-sensitive between commands but not inside expressions):

| Operator | Meaning | Example | Result |
|---|---|---|---|
| `+` `-` `*` `/` | add, subtract, multiply, real division | `WRITE 7/2,!` | `3.5` |
| `\` | integer division | `WRITE 7\2,!` | `3` |
| `#` | modulo | `WRITE 7#2,!` | `1` |
| `_` | string concatenation | `WRITE "ab"_"cd",!` | `abcd` |
| `=` | equals | `WRITE 5=5,!` | `1` |
| `'=` | not equal (leading `'` negates) | `WRITE 5'=5,!` | `0` |
| `>` `<` | greater/less than | `WRITE 5>3,!` | `1` |
| `&` | logical AND | `WRITE (5>3)&(2<1),!` | `0` |
| `!` | logical OR (only between two conditions; not the same `!` as WRITE's newline argument) | `WRITE (5>3)!(2<1),!` | `1` |

M has no boolean type -- every truth value is the integer `1` or `0`.

**There is no `>=` or `<=` operator.** A leading `'` negates the operator
that follows it, so "greater than or equal" is written `'<` (not less
than) and "less than or equal" is written `'>` (not greater than):

```m
WRITE 18'<18,!   ; 1 -- 18 is not less than 18
WRITE 17'<18,!   ; 0 -- 17 IS less than 18
```

## Conditionals: IF / ELSE (real gotcha, verified live)

`IF <condition> <commands...>` runs the rest of *that line* only if the
condition is true. **If the condition is false, M abandons the entire rest
of that line, not just the commands textually after the condition** -- so
`ELSE` chained on the *same* line as its `IF` never runs, because a false
`IF` never lets execution reach it:

```m
; WRONG -- "small" never prints; the false IF aborts the whole line,
; including the ELSE that comes after it on that same line.
IF 5>10 WRITE "big",! ELSE  WRITE "small",!

; RIGHT -- ELSE is its own line, so it's reached regardless of what the
; IF line above it did.
IF 5>10 WRITE "big",!
ELSE  WRITE "small",!
```

`ELSE` (note the double space before its command in the idiom above -- one
space separates commands, `ELSE` followed by two spaces then its command is
the traditional M style but a single space works identically) runs its
command only when the most recently evaluated condition (`$TEST`) was false.

## Loops: FOR

Three real forms, all verified live:

```m
; count-controlled: start:step:stop
FOR I=1:1:3 WRITE "i=",I,!

; argumentless FOR -- loops forever; QUIT (usually postconditional) breaks out.
; Everything else on the SAME line as an argumentless FOR is part of its
; loop body and repeats every iteration -- keep an argumentless FOR's line
; to just the loop body, and put code that should run once after the loop
; ends on the following line.
SET X=0
FOR  SET X=X+1 QUIT:X=5
WRITE X,!
```

`QUIT:X=5` is a postconditional `QUIT` -- the `:condition` after a command
runs that command only if the condition holds, same idea as `IF` but inline
on a single command rather than the rest of the line.

## String functions

Verified live against a real 3-piece comma-delimited string:

```m
SET S="one,two,three"
WRITE $LENGTH(S),!        ; 13 -- character count of the whole string
WRITE $EXTRACT(S,1,3),!   ; one -- substring, 1-indexed, inclusive
WRITE $PIECE(S,",",2),!   ; two -- 2nd field when split on ","
```

## Ending a program

`QUIT` with no argument ends a `FOR` loop early (see above). `HALT` ends the
whole job/session -- use it only when a task should stop before reaching
the end of its own source (e.g. mid-loop after finding an answer); a script
that simply runs to the end of its lines needs neither.
