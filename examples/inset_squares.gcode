; Outer square, 270 mm to a side
; Move into position
G0 X15Y15
; Laser on
M300 S255
G1 Y285
G1 X285
G1 Y15
G1 X15
;Laser off
M300 S0
; Inner square, 200 mm to a side
G0 X50Y50
; Laser on
M300 S255
G1 Y250
G1 X250
G1 Y50
G1 X50
;Laser off
M300 S0