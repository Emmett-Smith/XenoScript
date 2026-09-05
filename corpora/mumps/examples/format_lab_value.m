; $JUSTIFY(value,width[,decimals]) -- real formatting for aligned
; columns or fixed decimal places (lab values, currency).
WRITE $JUSTIFY(42,6),!         ; right-justified in a 6-char field
WRITE $JUSTIFY(3.5,0,2),!      ; forced to 2 decimal places -> 3.50
