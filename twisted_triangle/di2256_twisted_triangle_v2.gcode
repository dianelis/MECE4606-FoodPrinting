; Twisted Triangle Pyramid — Food Printing G-code
; Material: Peanut Butter (stiff paste)
;
; Recipe: Smooth peanut butter + ~10% powdered sugar
;         Warm to ~30°C before loading into syringe.
;
; Steps: 6 (each triangle printed 2× for rigidity)
; Total layers: 12
; Base radius: 20.0mm → Top radius: 6.0mm
; Twist per step: 15.0° (total: 75.0°)
; Layer height: 2.0mm
; Total height: 27.0mm
; Print speed: 300 mm/min
; Center: (100, 100)

; === INITIALIZATION ===
G21              ; Set units to millimeters
G90              ; Absolute positioning
M82              ; Absolute extrusion mode
G28              ; Home all axes


; ──── STEP 1/6 (R=20.0mm, θ=0.0°) × 2 layers ────

; --- Layer 1 (Z=5.0mm, step 1 rep 1/2) ---
G1 Z6.00 F600   ; Z-hop
G1 X120.000 Y100.000 F1200   ; Travel to start
G1 Z5.00 F300   ; Lower to layer height
G1 X90.000 Y117.321 E2.0785 F300   ; edge 1/3
G1 X90.000 Y82.679 E4.1569 F300   ; edge 2/3
G1 X120.000 Y100.000 E6.2354 F300   ; edge 3/3 (close)
G1 E4.7354 F1200   ; Retract

; --- Layer 2 (Z=7.0mm, step 1 rep 2/2) ---
G1 Z8.00 F600   ; Z-hop
G1 X120.000 Y100.000 F1200   ; Travel to start
G1 Z7.00 F300   ; Lower to layer height
G1 E6.2354 F1200   ; Prime
G1 X90.000 Y117.321 E8.3138 F300   ; edge 1/3
G1 X90.000 Y82.679 E10.3923 F300   ; edge 2/3
G1 X120.000 Y100.000 E12.4708 F300   ; edge 3/3 (close)
G1 E10.9708 F1200   ; Retract

; ──── STEP 2/6 (R=17.2mm, θ=15.0°) × 2 layers ────

; --- Layer 3 (Z=9.0mm, step 2 rep 1/2) ---
G1 Z10.00 F600   ; Z-hop
G1 X116.614 Y104.452 F1200   ; Travel to start
G1 Z9.00 F300   ; Lower to layer height
G1 E12.4708 F1200   ; Prime
G1 X87.838 Y112.162 E14.2582 F300   ; edge 1/3
G1 X95.548 Y83.386 E16.0457 F300   ; edge 2/3
G1 X116.614 Y104.452 E17.8332 F300   ; edge 3/3 (close)
G1 E16.3332 F1200   ; Retract

; --- Layer 4 (Z=11.0mm, step 2 rep 2/2) ---
G1 Z12.00 F600   ; Z-hop
G1 X116.614 Y104.452 F1200   ; Travel to start
G1 Z11.00 F300   ; Lower to layer height
G1 E17.8332 F1200   ; Prime
G1 X87.838 Y112.162 E19.6207 F300   ; edge 1/3
G1 X95.548 Y83.386 E21.4081 F300   ; edge 2/3
G1 X116.614 Y104.452 E23.1956 F300   ; edge 3/3 (close)
G1 E21.6956 F1200   ; Retract

; ──── STEP 3/6 (R=14.4mm, θ=30.0°) × 2 layers ────

; --- Layer 5 (Z=13.0mm, step 3 rep 1/2) ---
G1 Z14.00 F600   ; Z-hop
G1 X112.471 Y107.200 F1200   ; Travel to start
G1 Z13.00 F300   ; Lower to layer height
G1 E23.1956 F1200   ; Prime
G1 X87.529 Y107.200 E24.6921 F300   ; edge 1/3
G1 X100.000 Y85.600 E26.1886 F300   ; edge 2/3
G1 X112.471 Y107.200 E27.6851 F300   ; edge 3/3 (close)
G1 E26.1851 F1200   ; Retract

; --- Layer 6 (Z=15.0mm, step 3 rep 2/2) ---
G1 Z16.00 F600   ; Z-hop
G1 X112.471 Y107.200 F1200   ; Travel to start
G1 Z15.00 F300   ; Lower to layer height
G1 E27.6851 F1200   ; Prime
G1 X87.529 Y107.200 E29.1816 F300   ; edge 1/3
G1 X100.000 Y85.600 E30.6781 F300   ; edge 2/3
G1 X112.471 Y107.200 E32.1746 F300   ; edge 3/3 (close)
G1 E30.6746 F1200   ; Retract

; ──── STEP 4/6 (R=11.6mm, θ=45.0°) × 2 layers ────

; --- Layer 7 (Z=17.0mm, step 4 rep 1/2) ---
G1 Z18.00 F600   ; Z-hop
G1 X108.202 Y108.202 F1200   ; Travel to start
G1 Z17.00 F300   ; Lower to layer height
G1 E32.1746 F1200   ; Prime
G1 X88.795 Y103.002 E33.3801 F300   ; edge 1/3
G1 X103.002 Y88.795 E34.5856 F300   ; edge 2/3
G1 X108.202 Y108.202 E35.7911 F300   ; edge 3/3 (close)
G1 E34.2911 F1200   ; Retract

; --- Layer 8 (Z=19.0mm, step 4 rep 2/2) ---
G1 Z20.00 F600   ; Z-hop
G1 X108.202 Y108.202 F1200   ; Travel to start
G1 Z19.00 F300   ; Lower to layer height
G1 E35.7911 F1200   ; Prime
G1 X88.795 Y103.002 E36.9966 F300   ; edge 1/3
G1 X103.002 Y88.795 E38.2021 F300   ; edge 2/3
G1 X108.202 Y108.202 E39.4076 F300   ; edge 3/3 (close)
G1 E37.9076 F1200   ; Retract

; ──── STEP 5/6 (R=8.8mm, θ=60.0°) × 2 layers ────

; --- Layer 9 (Z=21.0mm, step 5 rep 1/2) ---
G1 Z22.00 F600   ; Z-hop
G1 X104.400 Y107.621 F1200   ; Travel to start
G1 Z21.00 F300   ; Lower to layer height
G1 E39.4076 F1200   ; Prime
G1 X91.200 Y100.000 E40.3221 F300   ; edge 1/3
G1 X104.400 Y92.379 E41.2367 F300   ; edge 2/3
G1 X104.400 Y107.621 E42.1512 F300   ; edge 3/3 (close)
G1 E40.6512 F1200   ; Retract

; --- Layer 10 (Z=23.0mm, step 5 rep 2/2) ---
G1 Z24.00 F600   ; Z-hop
G1 X104.400 Y107.621 F1200   ; Travel to start
G1 Z23.00 F300   ; Lower to layer height
G1 E42.1512 F1200   ; Prime
G1 X91.200 Y100.000 E43.0657 F300   ; edge 1/3
G1 X104.400 Y92.379 E43.9802 F300   ; edge 2/3
G1 X104.400 Y107.621 E44.8948 F300   ; edge 3/3 (close)
G1 E43.3948 F1200   ; Retract

; ──── STEP 6/6 (R=6.0mm, θ=75.0°) × 2 layers ────

; --- Layer 11 (Z=25.0mm, step 6 rep 1/2) ---
G1 Z26.00 F600   ; Z-hop
G1 X101.553 Y105.796 F1200   ; Travel to start
G1 Z25.00 F300   ; Lower to layer height
G1 E44.8948 F1200   ; Prime
G1 X94.204 Y98.447 E45.5183 F300   ; edge 1/3
G1 X104.243 Y95.757 E46.1418 F300   ; edge 2/3
G1 X101.553 Y105.796 E46.7654 F300   ; edge 3/3 (close)
G1 E45.2654 F1200   ; Retract

; --- Layer 12 (Z=27.0mm, step 6 rep 2/2) ---
G1 Z28.00 F600   ; Z-hop
G1 X101.553 Y105.796 F1200   ; Travel to start
G1 Z27.00 F300   ; Lower to layer height
G1 E46.7654 F1200   ; Prime
G1 X94.204 Y98.447 E47.3889 F300   ; edge 1/3
G1 X104.243 Y95.757 E48.0124 F300   ; edge 2/3
G1 X101.553 Y105.796 E48.6360 F300   ; edge 3/3 (close)
G1 E47.1360 F1200   ; Retract

; === FINISH ===
G1 Z47.0 F600      ; Raise nozzle clear
G1 X0 Y0 F1200   ; Move to home
M84              ; Disable motors

; === END ===
