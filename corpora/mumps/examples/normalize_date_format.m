; $TRANSLATE(string,fromChars,toChars) swaps characters one-for-one --
; a common real need when different systems expect different date
; separators.
WRITE $TRANSLATE("2024-01-15","-","/"),!
