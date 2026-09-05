; $DATA returns 0 when a global node doesn't exist -- the real M idiom
; for "does this record exist" before acting on it.
IF $DATA(^PATIENT(99))=0 WRITE "Patient not found",!
ELSE  WRITE "Patient exists: ",^PATIENT(99),!
