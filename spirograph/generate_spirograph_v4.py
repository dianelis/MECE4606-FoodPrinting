#!/usr/bin/env python3
"""
generate_spirograph_v4.py — Generate G-code for a 6-loop star epitrochoid.

Traces an epitrochoid (rolling circle outside) that produces a star pattern
with small loops at each point, matching a classic spirograph toy shape.

Usage:
    python generate_spirograph_v4.py
    python generate_spirograph_v4.py --layers 3 --twist 10
    python generate_spirograph_v4.py --help
"""

import argparse
import math
import os
import sys

# ─── Epitrochoid Defaults ────────────────────────────────────────────────────

# Epitrochoid: x = (R+r)cos(t) - d·cos((R+r)/r · t)
#              y = (R+r)sin(t) - d·sin((R+r)/r · t)
# R=18, r=3 → 6 loops; d=5 (d > r) → loops at cusps
# Max radius = R+r+d = 26mm → ~52mm diameter
BASE_R       = 18.0       # fixed circle radius
BASE_r       = 3.0        # rolling circle radius (rolls outside)
BASE_d       = 5.0        # pen offset (d > r gives loops)

# 3D stacking
NUM_LAYERS   = 3
TWIST_LAYER  = 10.0       # degrees rotation per layer
LAYER_HEIGHT = 2.0
FIRST_Z      = 6.0        # same as v3

# Resolution
POINTS_PER_REV = 360

# Print bed center
CENTER_X     = 100.0
CENTER_Y     = 100.0

# Print parameters
PRINT_SPEED  = 300
TRAVEL_SPEED = 1200
E_MULT       = 0.10
RETRACT      = 1.5
Z_HOP        = 1.0


# ─── Epitrochoid Math ──────────────────────────────────────────────────────

def epitrochoid_points(R, r, d, num_revs, total_points, cx, cy, rotation_deg=0):
    """Generate points along an epitrochoid.

    x = (R+r)·cos(t) - d·cos((R+r)/r · t)
    y = (R+r)·sin(t) - d·sin((R+r)/r · t)
    """
    rot = math.radians(rotation_deg)
    s = R + r
    ratio = s / r
    pts = []
    for i in range(total_points + 1):
        t = 2 * math.pi * num_revs * i / total_points
        x0 = s * math.cos(t) - d * math.cos(ratio * t)
        y0 = s * math.sin(t) - d * math.sin(ratio * t)
        # Rotate
        x = cx + x0 * math.cos(rot) - y0 * math.sin(rot)
        y = cy + x0 * math.sin(rot) + y0 * math.cos(rot)
        pts.append((x, y))
    return pts


def compute_num_revolutions(R, r):
    """Number of full revolutions of t to close the curve."""
    g = math.gcd(int(R), int(r))
    return int(r) // g


def compute_num_loops(R, r):
    """Number of loops / cusps in the pattern."""
    g = math.gcd(int(R), int(r))
    return int(R) // g


def seg_length(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


# ─── G-code Generator ───────────────────────────────────────────────────────

class EpitrochoidGenerator:
    def __init__(self, *, R, r, d, num_layers, twist_deg, layer_height,
                 first_z, pts_per_rev, cx, cy,
                 print_speed, travel_speed, e_mult, retract, z_hop):
        self.R = R
        self.r = r
        self.d = d
        self.num_layers = num_layers
        self.twist_deg = twist_deg
        self.layer_height = layer_height
        self.first_z = first_z
        self.pts_per_rev = pts_per_rev
        self.cx = cx
        self.cy = cy
        self.print_speed = print_speed
        self.travel_speed = travel_speed
        self.e_mult = e_mult
        self.retract = retract
        self.z_hop = z_hop

        self.lines = []
        self.e_total = 0.0
        self.current_z = 0.0
        self._retracted = False

        self.num_revs = compute_num_revolutions(R, r)
        self.num_loops = compute_num_loops(R, r)
        self.total_points = self.pts_per_rev * self.num_revs

    def generate(self) -> str:
        self._header()
        self._init_block()

        for layer_idx in range(self.num_layers):
            self._generate_layer(layer_idx)

        self._finish_block()
        return "\n".join(self.lines) + "\n"

    def _emit(self, line):
        self.lines.append(line)

    def _header(self):
        max_r = (self.R + self.r) + self.d
        min_r = abs((self.R + self.r) - self.d)
        total_height = self.first_z + (self.num_layers - 1) * self.layer_height
        total_twist = self.twist_deg * (self.num_layers - 1)
        self._emit("; 6-Loop Star Epitrochoid — Food Printing G-code (V4)")
        self._emit("; Single material per layer, stacked with twist")
        self._emit(";")
        self._emit(f"; Epitrochoid: R={self.R:.0f}, r={self.r:.0f}, d={self.d:.0f}")
        self._emit(f"; Formula: x = (R+r)cos(t) - d·cos((R+r)/r · t)")
        self._emit(f"; Loops: {self.num_loops}  |  Revolutions: {self.num_revs}")
        self._emit(f"; Pattern diameter: {max_r*2:.0f}mm (outer)")
        self._emit(f"; Points per layer: {self.total_points}")
        self._emit(f";")
        self._emit(f"; Layers: {self.num_layers}")
        self._emit(f"; Layer height: {self.layer_height:.1f}mm")
        self._emit(f"; Total height: {total_height:.1f}mm")
        self._emit(f"; Twist per layer: {self.twist_deg:.1f}° (total: {total_twist:.1f}°)")
        self._emit(f"; Print speed: {self.print_speed} mm/min")
        self._emit(f"; Center: ({self.cx:.0f}, {self.cy:.0f})")
        self._emit("")

    def _init_block(self):
        self._emit("; === INITIALIZATION ===")
        self._emit("G21              ; Set units to millimeters")
        self._emit("G90              ; Absolute positioning")
        self._emit("M82              ; Absolute extrusion mode")
        self._emit("G28              ; Home all axes")
        self._emit("")

    def _finish_block(self):
        self._emit("")
        self._emit("; === FINISH ===")
        final_z = self.current_z + 20
        self._emit(f"G1 Z{final_z:.1f} F600      ; Raise nozzle clear")
        self._emit(f"G1 X0 Y0 F{self.travel_speed}   ; Move to home")
        self._emit("M84              ; Disable motors")
        self._emit("")
        self._emit("; === END ===")

    def _generate_layer(self, layer_idx):
        z = self.first_z + layer_idx * self.layer_height
        self.current_z = z
        rotation = layer_idx * self.twist_deg

        self._emit("")
        self._emit(f"; === LAYER {layer_idx + 1}/{self.num_layers} "
                    f"(Z={z:.1f}mm, θ={rotation:.1f}°) ===")

        points = epitrochoid_points(
            self.R, self.r, self.d,
            self.num_revs, self.total_points,
            self.cx, self.cy,
            rotation_deg=rotation,
        )

        # Travel to first point
        x0, y0 = points[0]
        self._emit(f"G1 Z{z + self.z_hop:.2f} F600   ; Z-hop")
        self._emit(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Travel to start")
        self._emit(f"G1 Z{z:.2f} F300   ; Lower to layer height")

        # Prime
        if self._retracted:
            self.e_total += self.retract
            self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}   ; Prime")
            self._retracted = False

        # Trace the curve
        for i in range(1, len(points)):
            x_prev, y_prev = points[i - 1]
            x_cur, y_cur = points[i]
            d = seg_length(x_prev, y_prev, x_cur, y_cur)
            if d < 0.001:
                continue
            self.e_total += d * self.e_mult
            self._emit(f"G1 X{x_cur:.3f} Y{y_cur:.3f} "
                        f"E{self.e_total:.4f} F{self.print_speed}")

        # Retract
        self.e_total -= self.retract
        self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}   ; Retract")
        self._retracted = True


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate 6-loop star epitrochoid G-code (V4).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Traces an epitrochoid (rolling circle outside the fixed circle).
With d > r, the curve forms loops at each cusp — a classic spirograph star.

examples:
  %(prog)s                              Default: 6-loop star, 3 layers
  %(prog)s --layers 5 --twist 8         5 layers, 8° twist
  %(prog)s --R 24 --r 4 --d 7           6-loop variant, larger
  %(prog)s --R 20 --r 4 --d 6           5-loop star
""",
    )
    parser.add_argument("--R", type=float, default=BASE_R,
                        help=f"Fixed circle radius (default: {BASE_R})")
    parser.add_argument("--r", type=float, default=BASE_r,
                        help=f"Rolling circle radius (default: {BASE_r})")
    parser.add_argument("--d", type=float, default=BASE_d,
                        help=f"Pen offset (default: {BASE_d})")
    parser.add_argument("--layers", type=int, default=NUM_LAYERS,
                        help=f"Number of layers (default: {NUM_LAYERS})")
    parser.add_argument("--twist", type=float, default=TWIST_LAYER,
                        help=f"Rotation per layer in degrees (default: {TWIST_LAYER})")
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT,
                        help=f"Layer height in mm (default: {LAYER_HEIGHT})")
    parser.add_argument("--speed", type=int, default=PRINT_SPEED,
                        help=f"Print speed (default: {PRINT_SPEED})")
    parser.add_argument("--e-mult", type=float, default=E_MULT,
                        help=f"Extrusion multiplier (default: {E_MULT})")
    parser.add_argument("--resolution", type=int, default=POINTS_PER_REV,
                        help=f"Points per revolution (default: {POINTS_PER_REV})")
    parser.add_argument("-o", "--output", default=None,
                        help="Output file path")

    args = parser.parse_args()

    gen = EpitrochoidGenerator(
        R=args.R, r=args.r, d=args.d,
        num_layers=args.layers,
        twist_deg=args.twist,
        layer_height=args.layer_height,
        first_z=FIRST_Z,
        pts_per_rev=args.resolution,
        cx=CENTER_X, cy=CENTER_Y,
        print_speed=args.speed,
        travel_speed=TRAVEL_SPEED,
        e_mult=args.e_mult,
        retract=RETRACT,
        z_hop=Z_HOP,
    )

    gcode = gen.generate()

    if args.output:
        out_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(script_dir, "di2256_spirograph_v4.gcode")

    with open(out_path, "w") as f:
        f.write(gcode)

    loops = compute_num_loops(args.R, args.r)
    revs = compute_num_revolutions(args.R, args.r)
    total_height = FIRST_Z + (args.layers - 1) * args.layer_height
    total_twist = args.twist * (args.layers - 1)
    max_d = (args.R + args.r + args.d) * 2

    print(f"✓ Generated: {out_path}")
    print(f"  {loops}-loop star epitrochoid, {revs} revolution(s)")
    print(f"  Diameter: ~{max_d:.0f}mm")
    print(f"  {args.layers} layers, {total_height:.1f}mm tall")
    print(f"  Twist: {args.twist:.1f}°/layer → {total_twist:.1f}° total")


if __name__ == "__main__":
    main()
