; $LENGTH, $EXTRACT, $PIECE, and _ (concatenation).
SET S="alpha,beta,gamma"
WRITE $LENGTH(S),!
WRITE $EXTRACT(S,1,5),!
WRITE $PIECE(S,",",2),!
WRITE "first="_$PIECE(S,",",1),!
