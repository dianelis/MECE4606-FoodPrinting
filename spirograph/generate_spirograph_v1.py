#!/usr/bin/env python3
"""
generate_spirograph_v1.py — Single-ring spirograph (hypotrochoid).

Traces one spirograph curve per layer, stacked with twist.
Material switches every N layers between 2 syringes.

Usage:
    python generate_spirograph_v1.py
    python generate_spirograph_v1.py --R 30 --r 12 --d 8 --layers 10
"""

import argparse
import math
import os
import sys

# ─── Defaults ────────────────────────────────────────────────────────────────

FIXED_R      = 30.0
ROLLING_R    = 12.0
PEN_D        = 8.0

NUM_LAYERS   = 10
TWIST_LAYER  = 6.0
LAYER_HEIGHT = 2.0
FIRST_Z      = 2.0

POINTS_PER_REV = 180

CENTER_X     = 100.0
CENTER_Y     = 100.0

PRINT_SPEED  = 300
TRAVEL_SPEED = 1200
E_MULT       = 0.10
RETRACT      = 1.5
Z_HOP        = 1.0

SWITCH_EVERY = 2


# ─── Math ────────────────────────────────────────────────────────────────────

def hypotrochoid_point(R, r, d, t, cx=0, cy=0, rotation_deg=0):
    rot = math.radians(rotation_deg)
    diff = R - r
    ratio = diff / r
    x0 = diff * math.cos(t) + d * math.cos(ratio * t)
    y0 = diff * math.sin(t) - d * math.sin(ratio * t)
    x = cx + x0 * math.cos(rot) - y0 * math.sin(rot)
    y = cy + x0 * math.sin(rot) + y0 * math.cos(rot)
    return x, y


def compute_num_revolutions(R, r):
    g = math.gcd(int(R), int(r))
    return int(r) // g


def compute_num_petals(R, r):
    g = math.gcd(int(R), int(r))
    return int(R) // g


def seg_length(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


# ─── Generator ───────────────────────────────────────────────────────────────

class SpirographGenerator:
    def __init__(self, *, R, r, d, num_layers, twist_deg, layer_height,
                 first_z, points_per_rev, center_x, center_y,
                 print_speed, travel_speed, e_mult, retract, z_hop,
                 switch_every):
        self.R = R
        self.r = r
        self.d = d
        self.num_layers = num_layers
        self.twist_deg = twist_deg
        self.layer_height = layer_height
        self.first_z = first_z
        self.pts_per_rev = points_per_rev
        self.cx = center_x
        self.cy = center_y
        self.print_speed = print_speed
        self.travel_speed = travel_speed
        self.e_mult = e_mult
        self.retract = retract
        self.z_hop = z_hop
        self.switch_every = switch_every

        self.lines = []
        self.e_total = 0.0
        self.current_z = 0.0
        self._retracted = False
        self.current_material = "A"

        self.num_revolutions = compute_num_revolutions(R, r)
        self.num_petals = compute_num_petals(R, r)
        self.total_points = self.pts_per_rev * self.num_revolutions

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
        max_ext = (self.R - self.r) + self.d
        min_ext = abs((self.R - self.r) - self.d)
        total_height = self.first_z + (self.num_layers - 1) * self.layer_height
        total_twist = self.twist_deg * (self.num_layers - 1)
        self._emit("; Spirograph V1 (Single-Ring Hypotrochoid) — Food Printing")
        self._emit("; Multi-material: 2 syringe colors")
        self._emit(";")
        self._emit("; Material A: Cream Cheese (plain)")
        self._emit("; Material B: Cream Cheese + food coloring")
        self._emit(";")
        self._emit(f"; Hypotrochoid: R={self.R:.0f}, r={self.r:.0f}, d={self.d:.0f}")
        self._emit(f"; Petals: {self.num_petals}  |  Revolutions: {self.num_revolutions}")
        self._emit(f"; Pattern diameter: {min_ext*2:.0f}mm (inner) to {max_ext*2:.0f}mm (outer)")
        self._emit(f"; Points per layer: {self.total_points}")
        self._emit(f";")
        self._emit(f"; Layers: {self.num_layers}  |  Layer height: {self.layer_height:.1f}mm")
        self._emit(f"; Total height: {total_height:.1f}mm")
        self._emit(f"; Twist per layer: {self.twist_deg:.1f}° (total: {total_twist:.1f}°)")
        self._emit(f"; Material switch every {self.switch_every} layers")
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
        self._emit("; Load Material A (plain cream cheese)")
        self._emit("; >>> SYRINGE: Material A <<<")
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

        if layer_idx > 0 and layer_idx % self.switch_every == 0:
            new_mat = "B" if self.current_material == "A" else "A"
            self._emit("")
            self._emit(f"; *** MATERIAL SWITCH: {self.current_material} → {new_mat} ***")
            self._emit(f"; >>> PAUSE: Switch to syringe {new_mat} <<<")
            self._emit(f"M0               ; Pause for syringe swap")
            self._emit(f"; >>> SYRINGE: Material {new_mat} <<<")
            self.current_material = new_mat

        self._emit("")
        self._emit(f"; === LAYER {layer_idx + 1}/{self.num_layers} "
                    f"(Z={z:.1f}mm, θ={rotation:.1f}°, Material {self.current_material}) ===")

        points = []
        for i in range(self.total_points + 1):
            t = 2 * math.pi * self.num_revolutions * i / self.total_points
            x, y = hypotrochoid_point(
                self.R, self.r, self.d, t,
                cx=self.cx, cy=self.cy,
                rotation_deg=rotation
            )
            points.append((x, y))

        x0, y0 = points[0]
        self._emit(f"G1 Z{z + self.z_hop:.2f} F600   ; Z-hop")
        self._emit(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Travel to start")
        self._emit(f"G1 Z{z:.2f} F300   ; Lower to layer height")

        if self._retracted:
            self.e_total += self.retract
            self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}   ; Prime")
            self._retracted = False

        for i in range(1, len(points)):
            x_prev, y_prev = points[i - 1]
            x_cur, y_cur = points[i]
            d = seg_length(x_prev, y_prev, x_cur, y_cur)
            if d < 0.001:
                continue
            self.e_total += d * self.e_mult
            self._emit(f"G1 X{x_cur:.3f} Y{y_cur:.3f} "
                        f"E{self.e_total:.4f} F{self.print_speed}")

        self.e_total -= self.retract
        self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}   ; Retract")
        self._retracted = True


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate single-ring spirograph G-code (V1).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--R", type=float, default=FIXED_R)
    parser.add_argument("--r", type=float, default=ROLLING_R)
    parser.add_argument("--d", type=float, default=PEN_D)
    parser.add_argument("--layers", type=int, default=NUM_LAYERS)
    parser.add_argument("--twist", type=float, default=TWIST_LAYER)
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT)
    parser.add_argument("--speed", type=int, default=PRINT_SPEED)
    parser.add_argument("--e-mult", type=float, default=E_MULT)
    parser.add_argument("--switch-every", type=int, default=SWITCH_EVERY)
    parser.add_argument("--resolution", type=int, default=POINTS_PER_REV)
    parser.add_argument("-o", "--output", default=None)

    args = parser.parse_args()

    gen = SpirographGenerator(
        R=args.R, r=args.r, d=args.d,
        num_layers=args.layers,
        twist_deg=args.twist,
        layer_height=args.layer_height,
        first_z=FIRST_Z,
        points_per_rev=args.resolution,
        center_x=CENTER_X, center_y=CENTER_Y,
        print_speed=args.speed,
        travel_speed=TRAVEL_SPEED,
        e_mult=args.e_mult,
        retract=RETRACT,
        z_hop=Z_HOP,
        switch_every=args.switch_every,
    )

    gcode = gen.generate()

    if args.output:
        out_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(script_dir, "di2256_spirograph_v1.gcode")

    with open(out_path, "w") as f:
        f.write(gcode)

    petals = compute_num_petals(args.R, args.r)
    revs = compute_num_revolutions(args.R, args.r)
    total_height = FIRST_Z + (args.layers - 1) * args.layer_height
    total_twist = args.twist * (args.layers - 1)

    print(f"✓ V1 Generated: {out_path}")
    print(f"  {petals} petals, {revs} revolutions per layer")
    print(f"  {args.layers} layers, {total_height:.1f}mm tall")
    print(f"  Twist: {args.twist:.1f}°/layer → {total_twist:.1f}° total")


if __name__ == "__main__":
    main()
