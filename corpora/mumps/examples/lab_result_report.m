; Iterating a global array with FOR/$ORDER -- the standard M pattern for
; walking every record of something, here a small set of lab results.
; The whole loop body must stay on the FOR line itself (see docs/manual.md
; -- and dotted-DO blocks don't work in this corpus's direct-mode
; execution, so there is no multi-line alternative here).
SET ^LAB(1)="GLUCOSE^145^HIGH"
SET ^LAB(2)="POTASSIUM^4.1^NORMAL"
SET ^LAB(3)="SODIUM^138^NORMAL"
SET IDX=""
FOR  SET IDX=$ORDER(^LAB(IDX)) QUIT:IDX=""  WRITE $PIECE(^LAB(IDX),"^",1),": ",$PIECE(^LAB(IDX),"^",2)," (",$PIECE(^LAB(IDX),"^",3),")",!
