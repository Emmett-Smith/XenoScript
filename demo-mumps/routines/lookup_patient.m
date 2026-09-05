; Reads patient #1 -- sets nothing. If this prints a real name, the
; record genuinely survived from a previous, separate run.sh invocation.
SET REC=^PATIENT(1)
WRITE "NAME: ",$PIECE(REC,"^",1),!
WRITE "AGE: ",$PIECE(REC,"^",2),!
WRITE "SEX: ",$PIECE(REC,"^",3),!
