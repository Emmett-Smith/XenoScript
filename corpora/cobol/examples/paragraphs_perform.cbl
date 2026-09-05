*> paragraphs_perform.cbl -- demonstrates: factoring PROCEDURE DIVISION
*> code into named paragraphs and invoking them with PERFORM
*> paragraph-name, including PERFORM paragraph-name TIMES.
IDENTIFICATION DIVISION.
PROGRAM-ID. PARAPERFORM.

PROCEDURE DIVISION.
MAIN-LOGIC.
    DISPLAY "STARTING".
    PERFORM PRINT-GREETING.
    PERFORM PRINT-GREETING 2 TIMES.
    DISPLAY "DONE".
    STOP RUN.

PRINT-GREETING.
    DISPLAY "HELLO FROM A PARAGRAPH".
