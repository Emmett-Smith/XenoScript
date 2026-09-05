; Run this once to seed the hospital database with starting records.
; Real M globals (^name) are stored on disk in db/hospital.dat -- after
; this runs, every other routine in this folder can see this data, in a
; completely separate process invocation, proving it's a real database
; and not just a script re-running itself.
SET ^PATIENT(1)="DOE,JANE^34^F"
SET ^PATIENT(2)="SMITH,JOHN^58^M"
WRITE "Seeded 2 patient records.",!
