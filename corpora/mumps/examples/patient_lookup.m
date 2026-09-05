; Patient records stored as pieces in a global array, keyed by patient ID.
; ^name is a global -- M's persistent, disk-backed database, the feature
; that made it the dominant EHR language (VistA, Epic, Meditech all use it).
SET ^PATIENT(1)="DOE,JANE^34^F"
SET ^PATIENT(2)="SMITH,JOHN^58^M"
SET REC=^PATIENT(1)
WRITE "NAME: ",$PIECE(REC,"^",1),!
WRITE "AGE: ",$PIECE(REC,"^",2),!
WRITE "SEX: ",$PIECE(REC,"^",3),!
