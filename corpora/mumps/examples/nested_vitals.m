; Real EHR records are rarely one flat string -- multi-level subscripts
; (^global(id,"category","field")) are the standard M pattern for
; structured records. Vitals nested under a patient ID, by field name.
SET ^PATIENT(10,"NAME")="GARCIA,MARIA"
SET ^PATIENT(10,"VITALS","HR")=88
SET ^PATIENT(10,"VITALS","TEMP")=98.6
WRITE ^PATIENT(10,"NAME"),!
WRITE "HR: ",^PATIENT(10,"VITALS","HR"),!
