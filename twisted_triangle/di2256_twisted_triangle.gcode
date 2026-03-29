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
; Total height: 24.0mm
; Print speed: 300 mm/min
; Center: (100, 100)

; === INITIALIZATION ===
G21              ; Set units to millimeters
G90              ; Absolute positioning
M82              ; Absolute extrusion mode
G28              ; Home all axes


; ──── STEP 1/6 (R=20.0mm, θ=0.0°) × 2 layers ────

; --- Layer 1 (Z=2.0mm, step 1 rep 1/2) ---
G1 Z3.00 F600   ; Z-hop
G1 X120.000 Y100.000 F1200   ; Travel to start
G1 Z2.00 F300   ; Lower to layer height
G1 X90.000 Y117.321 E4.1569 F300   ; edge 1/3
G1 X90.000 Y82.679 E8.3138 F300   ; edge 2/3
G1 X120.000 Y100.000 E12.4708 F300   ; edge 3/3 (close)
G1 E10.9708 F1200   ; Retract

; --- Layer 2 (Z=4.0mm, step 1 rep 2/2) ---
G1 Z5.00 F600   ; Z-hop
G1 X120.000 Y100.000 F1200   ; Travel to start
G1 Z4.00 F300   ; Lower to layer height
G1 E12.4708 F1200   ; Prime
G1 X90.000 Y117.321 E16.6277 F300   ; edge 1/3
G1 X90.000 Y82.679 E20.7846 F300   ; edge 2/3
G1 X120.000 Y100.000 E24.9415 F300   ; edge 3/3 (close)
G1 E23.4415 F1200   ; Retract

; ──── STEP 2/6 (R=17.2mm, θ=15.0°) × 2 layers ────

; --- Layer 3 (Z=6.0mm, step 2 rep 1/2) ---
G1 Z7.00 F600   ; Z-hop
G1 X116.614 Y104.452 F1200   ; Travel to start
G1 Z6.00 F300   ; Lower to layer height
G1 E24.9415 F1200   ; Prime
G1 X87.838 Y112.162 E28.5165 F300   ; edge 1/3
G1 X95.548 Y83.386 E32.0914 F300   ; edge 2/3
G1 X116.614 Y104.452 E35.6664 F300   ; edge 3/3 (close)
G1 E34.1664 F1200   ; Retract

; --- Layer 4 (Z=8.0mm, step 2 rep 2/2) ---
G1 Z9.00 F600   ; Z-hop
G1 X116.614 Y104.452 F1200   ; Travel to start
G1 Z8.00 F300   ; Lower to layer height
G1 E35.6664 F1200   ; Prime
G1 X87.838 Y112.162 E39.2413 F300   ; edge 1/3
G1 X95.548 Y83.386 E42.8163 F300   ; edge 2/3
G1 X116.614 Y104.452 E46.3912 F300   ; edge 3/3 (close)
G1 E44.8912 F1200   ; Retract

; ──── STEP 3/6 (R=14.4mm, θ=30.0°) × 2 layers ────

; --- Layer 5 (Z=10.0mm, step 3 rep 1/2) ---
G1 Z11.00 F600   ; Z-hop
G1 X112.471 Y107.200 F1200   ; Travel to start
G1 Z10.00 F300   ; Lower to layer height
G1 E46.3912 F1200   ; Prime
G1 X87.529 Y107.200 E49.3842 F300   ; edge 1/3
G1 X100.000 Y85.600 E52.3772 F300   ; edge 2/3
G1 X112.471 Y107.200 E55.3702 F300   ; edge 3/3 (close)
G1 E53.8702 F1200   ; Retract

; --- Layer 6 (Z=12.0mm, step 3 rep 2/2) ---
G1 Z13.00 F600   ; Z-hop
G1 X112.471 Y107.200 F1200   ; Travel to start
G1 Z12.00 F300   ; Lower to layer height
G1 E55.3702 F1200   ; Prime
G1 X87.529 Y107.200 E58.3632 F300   ; edge 1/3
G1 X100.000 Y85.600 E61.3562 F300   ; edge 2/3
G1 X112.471 Y107.200 E64.3492 F300   ; edge 3/3 (close)
G1 E62.8492 F1200   ; Retract

; ──── STEP 4/6 (R=11.6mm, θ=45.0°) × 2 layers ────

; --- Layer 7 (Z=14.0mm, step 4 rep 1/2) ---
G1 Z15.00 F600   ; Z-hop
G1 X108.202 Y108.202 F1200   ; Travel to start
G1 Z14.00 F300   ; Lower to layer height
G1 E64.3492 F1200   ; Prime
G1 X88.795 Y103.002 E66.7602 F300   ; edge 1/3
G1 X103.002 Y88.795 E69.1712 F300   ; edge 2/3
G1 X108.202 Y108.202 E71.5822 F300   ; edge 3/3 (close)
G1 E70.0822 F1200   ; Retract

; --- Layer 8 (Z=16.0mm, step 4 rep 2/2) ---
G1 Z17.00 F600   ; Z-hop
G1 X108.202 Y108.202 F1200   ; Travel to start
G1 Z16.00 F300   ; Lower to layer height
G1 E71.5822 F1200   ; Prime
G1 X88.795 Y103.002 E73.9932 F300   ; edge 1/3
G1 X103.002 Y88.795 E76.4042 F300   ; edge 2/3
G1 X108.202 Y108.202 E78.8152 F300   ; edge 3/3 (close)
G1 E77.3152 F1200   ; Retract

; ──── STEP 5/6 (R=8.8mm, θ=60.0°) × 2 layers ────

; --- Layer 9 (Z=18.0mm, step 5 rep 1/2) ---
G1 Z19.00 F600   ; Z-hop
G1 X104.400 Y107.621 F1200   ; Travel to start
G1 Z18.00 F300   ; Lower to layer height
G1 E78.8152 F1200   ; Prime
G1 X91.200 Y100.000 E80.6443 F300   ; edge 1/3
G1 X104.400 Y92.379 E82.4733 F300   ; edge 2/3
G1 X104.400 Y107.621 E84.3024 F300   ; edge 3/3 (close)
G1 E82.8024 F1200   ; Retract

; --- Layer 10 (Z=20.0mm, step 5 rep 2/2) ---
G1 Z21.00 F600   ; Z-hop
G1 X104.400 Y107.621 F1200   ; Travel to start
G1 Z20.00 F300   ; Lower to layer height
G1 E84.3024 F1200   ; Prime
G1 X91.200 Y100.000 E86.1314 F300   ; edge 1/3
G1 X104.400 Y92.379 E87.9605 F300   ; edge 2/3
G1 X104.400 Y107.621 E89.7895 F300   ; edge 3/3 (close)
G1 E88.2895 F1200   ; Retract

; ──── STEP 6/6 (R=6.0mm, θ=75.0°) × 2 layers ────

; --- Layer 11 (Z=22.0mm, step 6 rep 1/2) ---
G1 Z23.00 F600   ; Z-hop
G1 X101.553 Y105.796 F1200   ; Travel to start
G1 Z22.00 F300   ; Lower to layer height
G1 E89.7895 F1200   ; Prime
G1 X94.204 Y98.447 E91.0366 F300   ; edge 1/3
G1 X104.243 Y95.757 E92.2837 F300   ; edge 2/3
G1 X101.553 Y105.796 E93.5307 F300   ; edge 3/3 (close)
G1 E92.0307 F1200   ; Retract

; --- Layer 12 (Z=24.0mm, step 6 rep 2/2) ---
G1 Z25.00 F600   ; Z-hop
G1 X101.553 Y105.796 F1200   ; Travel to start
G1 Z24.00 F300   ; Lower to layer height
G1 E93.5307 F1200   ; Prime
G1 X94.204 Y98.447 E94.7778 F300   ; edge 1/3
G1 X104.243 Y95.757 E96.0249 F300   ; edge 2/3
G1 X101.553 Y105.796 E97.2720 F300   ; edge 3/3 (close)
G1 E95.7720 F1200   ; Retract

; === FINISH ===
G1 Z44.0 F600      ; Raise nozzle clear
G1 X0 Y0 F1200   ; Move to home
M84              ; Disable motors

; === END ===
