; A false IF abandons the rest of its own line, including an ELSE chained
; on that same line -- ELSE must be its own line to ever be reached.
SET SCORE=42
IF SCORE>50 WRITE "high",!
ELSE  WRITE "low",!
