; Lists every patient currently in the database, using the standard
; M pattern for walking a global array: FOR + $ORDER.
SET ID=""
FOR  SET ID=$ORDER(^PATIENT(ID)) QUIT:ID=""  WRITE ID,": ",$PIECE(^PATIENT(ID),"^",1)," (age ",$PIECE(^PATIENT(ID),"^",2),")",!
