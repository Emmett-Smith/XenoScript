; KILL removes a global node entirely -- the real M way to delete a
; record. $DATA confirms it's actually gone (0 means "no such node").
SET ^PATIENT(5)="TEMP,PATIENT^40^M"
WRITE "before: ",$DATA(^PATIENT(5)),!
KILL ^PATIENT(5)
WRITE "after: ",$DATA(^PATIENT(5)),!
