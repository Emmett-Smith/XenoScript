; Threshold checks against vital signs, using the real '< ("not less
; than") idiom -- M has no >= operator, see docs/manual.md.
SET HEARTRATE=118
SET TEMP=101.4
IF HEARTRATE'<100 WRITE "ALERT: TACHYCARDIA (HR=",HEARTRATE,")",!
ELSE  WRITE "HEART RATE NORMAL",!
IF TEMP'<100.4 WRITE "ALERT: FEVER (TEMP=",TEMP,")",!
ELSE  WRITE "TEMPERATURE NORMAL",!
