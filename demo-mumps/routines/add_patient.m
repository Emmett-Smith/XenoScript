; Adds one new patient record with the next free ID, using $ORDER to
; find the current highest ID already in the database -- a real M
; idiom, not a fixed/hardcoded ID. Run this more than once and watch
; the database actually grow.
SET NEXTID=$ORDER(^PATIENT(""),-1)+1
SET ^PATIENT(NEXTID)="LEE,KIM^27^F"
WRITE "Added patient ",NEXTID,".",!
