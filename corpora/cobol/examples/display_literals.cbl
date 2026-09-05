*> display_literals.cbl -- demonstrates: multiple DISPLAY statements with
*> string literals, and concatenating a literal with itself across two
*> DISPLAY calls to show that each DISPLAY ends with its own newline.
IDENTIFICATION DIVISION.
PROGRAM-ID. DISPLAYLIT.

PROCEDURE DIVISION.
    DISPLAY "FIRST LINE".
    DISPLAY "SECOND LINE".
    DISPLAY "THIRD LINE WITH A NUMBER: " 42.
    STOP RUN.
