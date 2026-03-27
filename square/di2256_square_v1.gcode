; Simple Square - Food Printing G-code
; Square size: 40mm x 40mm
; Layer height: 1.0mm
; Nozzle diameter: ~1.0mm (food extrusion)
; Print speed: 600 mm/min (10 mm/s)
; Extrusion speed: 300 mm/min (5 mm/s)

; === INITIALIZATION ===
G21              ; Set units to millimeters
G90              ; Absolute positioning
M82              ; Absolute extrusion mode
G28              ; Home all axes

; === MOVE TO START POSITION ===
G1 Z5 F600       ; Raise nozzle 5mm
G1 X80 Y80 F1200 ; Move to start corner (centered on ~200mm bed)
G1 Z1.0 F600     ; Lower to first layer height

; === RESET EXTRUSION ===
G92 E0           ; Reset extruder position

; === LAYER 1 - SQUARE (40mm x 40mm) ===
; Bottom edge (left to right)
G1 X120 Y80 E4.0 F600

; Right edge (bottom to top)
G1 X120 Y120 E8.0 F600

; Top edge (right to left)
G1 X80 Y120 E12.0 F600

; Left edge (top to bottom, closing the square)
G1 X80 Y80 E16.0 F600

; === FINISH ===
G1 E15.5 F1200   ; Retract slightly to reduce ooze
G1 Z10 F600      ; Raise nozzle
G1 X0 Y0 F1200   ; Move to home position
M84              ; Disable motors

; === END ===
