*> loop_perform_until.cbl -- demonstrates: PERFORM ... UNTIL as a
*> while-style loop, with a manually maintained counter (MOVE to
*> initialize, ADD to increment inside the loop body).
IDENTIFICATION DIVISION.
PROGRAM-ID. LOOPUNTIL.

DATA DIVISION.
WORKING-STORAGE SECTION.
01  WS-INDEX  PIC 9(2) VALUE 0.

PROCEDURE DIVISION.
    MOVE 1 TO WS-INDEX.
    PERFORM UNTIL WS-INDEX > 5
        DISPLAY "COUNT IS " WS-INDEX
        ADD 1 TO WS-INDEX
    END-PERFORM.
    DISPLAY "FINAL INDEX: " WS-INDEX.
    STOP RUN.
