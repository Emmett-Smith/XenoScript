; $FIND locates a substring (returning the position right after the
; match), combined with $EXTRACT to pull out everything before it --
; the real M way to split "LAST,FIRST" without a dedicated split function.
SET FULLNAME="GARCIA,MARIA"
SET COMMAPOS=$FIND(FULLNAME,",")
SET LASTNAME=$EXTRACT(FULLNAME,1,COMMAPOS-2)
WRITE "LAST NAME: ",LASTNAME,!
