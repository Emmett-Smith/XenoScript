*> loop_perform_times.cbl -- demonstrates: the counted PERFORM ... TIMES
*> loop, and PERFORM VARYING for a counted loop that also exposes an
*> index variable inside the loop body.
IDENTIFICATION DIVISION.
PROGRAM-ID. LOOPTIMES.

DATA DIVISION.
WORKING-STORAGE SECTION.
01  WS-INDEX  PIC 9(2) VALUE 1.

PROCEDURE DIVISION.
    PERFORM 3 TIMES
        DISPLAY "HELLO"
    END-PERFORM.

    PERFORM VARYING WS-INDEX FROM 1 BY 1 UNTIL WS-INDEX > 5
        DISPLAY "COUNT IS " WS-INDEX
    END-PERFORM.
    STOP RUN.
