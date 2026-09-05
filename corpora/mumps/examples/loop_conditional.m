; Argumentless FOR with a postconditional QUIT to break out. Everything on
; the FOR's own line is the loop body -- code that should run once after
; the loop ends goes on the next line, not the same one.
SET COUNT=0
FOR  SET COUNT=COUNT+1 QUIT:COUNT=5
WRITE "final count=",COUNT,!
