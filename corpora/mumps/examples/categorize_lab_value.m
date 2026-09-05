; $SELECT is M's multi-way branch (there is no ELSEIF) -- each
; condition:value pair is checked in order, first true one wins. "1:"
; as the last pair is the conventional default/else case.
SET GLUCOSE=145
SET CATEGORY=$SELECT(GLUCOSE<70:"LOW",GLUCOSE>140:"HIGH",1:"NORMAL")
WRITE CATEGORY,!
