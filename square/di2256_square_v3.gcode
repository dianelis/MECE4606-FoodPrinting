; Simple Square - Food Printing G-code (Cream Cheese)
; Square size: 40mm x 40mm
; Layer height: 3.0mm
; Extrusion: 4.0mm per edge (uniform)
; Print speed: 400 mm/min

; === INITIALIZATION ===
G21              ; Set units to millimeters
G90              ; Absolute positioning
M82              ; Absolute extrusion mode
G28              ; Home all axes

; === MOVE TO START POSITION ===
G1 Z10 F600      ; Raise nozzle 10mm for safe travel
G1 X80 Y80 F1200 ; Move to start corner
G1 Z3.0 F300     ; Lower to layer height (3mm above plate)

; === RESET EXTRUSION ===
G92 E0           ; Reset extruder position

; === LAYER 1 - SQUARE (40mm x 40mm) ===
; Bottom edge (left to right)
G1 X120 Y80 E4.0 F400

; Right edge (bottom to top)
G1 X120 Y120 E8.0 F400

; Top edge (right to left)
G1 X80 Y120 E12.0 F400

; Left edge (top to bottom, closing the square)
G1 X80 Y80 E16.0 F400

; === FINISH ===
G1 E15.0 F1200   ; Retract to reduce ooze
G1 Z15 F600      ; Raise nozzle
G1 X0 Y0 F1200   ; Move to home position
M84              ; Disable motors

; === END ===
