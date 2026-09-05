*> classify_grade.cbl -- demonstrates: chained IF/ELSE IF/ELSE (more than
*> two branches, unlike conditional_if_else.cbl's plain two-way IF), used
*> to classify a numeric score into a letter grade.
IDENTIFICATION DIVISION.
PROGRAM-ID. CLASSIFYGRADE.

DATA DIVISION.
WORKING-STORAGE SECTION.
01  WS-SCORE   PIC 9(3) VALUE 87.
01  WS-GRADE   PIC X    VALUE SPACE.

PROCEDURE DIVISION.
    IF WS-SCORE >= 90
        MOVE "A" TO WS-GRADE
    ELSE
        IF WS-SCORE >= 80
            MOVE "B" TO WS-GRADE
        ELSE
            IF WS-SCORE >= 70
                MOVE "C" TO WS-GRADE
            ELSE
                MOVE "F" TO WS-GRADE
            END-IF
        END-IF
    END-IF.
    DISPLAY "SCORE: " WS-SCORE.
    DISPLAY "GRADE: " WS-GRADE.
    STOP RUN.
