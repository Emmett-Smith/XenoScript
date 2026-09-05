; Walking every field at a nested subscript level -- the same FOR/$ORDER
; pattern as list_patients.m, one level deeper.
SET ^PATIENT(10,"VITALS","HR")=88
SET ^PATIENT(10,"VITALS","TEMP")=98.6
SET ^PATIENT(10,"VITALS","BP")=120
SET FIELD=""
FOR  SET FIELD=$ORDER(^PATIENT(10,"VITALS",FIELD)) QUIT:FIELD=""  WRITE FIELD,": ",^PATIENT(10,"VITALS",FIELD),!
