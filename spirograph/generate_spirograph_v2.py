#!/usr/bin/env python3
"""
generate_spirograph.py — Generate G-code for a 3-color nested spirograph.

Prints 3 concentric hypotrochoid spirographs on each layer:
  - Outer ring  (Material A — cyan/teal, e.g. cream cheese + blue dye)
  - Middle ring (Material B — pink/red,   e.g. cream cheese + beet powder)
  - Inner ring  (Material C — purple,     e.g. cream cheese + ube/grape dye)

Each layer prints all 3 rings, with M0 pause for syringe swaps between rings.
Multiple layers can be stacked with a twist for a 3D spirograph tower.

Usage:
    python generate_spirograph.py
    python generate_spirograph.py --layers 3 --twist 10
    python generate_spirograph.py --help
"""

import argparse
import math
import os
import sys

# ─── Spirograph / Hypotrochoid Defaults ──────────────────────────────────────

# Base hypotrochoid shape: R=30, r=12, d=8 → 5 petals
BASE_R       = 30.0
BASE_r       = 12.0
BASE_d       = 8.0

# 3 concentric scales (fraction of the base pattern)
SCALE_OUTER  = 1.0        # ~52mm diameter
SCALE_MIDDLE = 0.68       # ~35mm diameter
SCALE_INNER  = 0.40       # ~21mm diameter

# 3D stacking
NUM_LAYERS   = 3          # layers (kept small to limit syringe swaps)
TWIST_LAYER  = 12.0       # degrees to rotate the whole pattern per layer
LAYER_HEIGHT = 2.0
FIRST_Z      = 2.0

# Resolution
POINTS_PER_REV = 180

# Print bed center
CENTER_X     = 100.0
CENTER_Y     = 100.0

# Print parameters
PRINT_SPEED  = 300
TRAVEL_SPEED = 1200
E_MULT       = 0.10
RETRACT      = 1.5
Z_HOP        = 1.0

# Material labels
MATERIALS = [
    ("A", "Cream Cheese + blue dye (teal)"),
    ("B", "Cream Cheese + beet powder (pink)"),
    ("C", "Cream Cheese + ube extract (purple)"),
]


# ─── Hypotrochoid Math ──────────────────────────────────────────────────────

def hypotrochoid_points(R, r, d, num_revs, total_points, cx, cy, rotation_deg, scale):
    """Generate points along a scaled, rotated hypotrochoid."""
    rot = math.radians(rotation_deg)
    diff = R - r
    ratio = diff / r
    pts = []
    for i in range(total_points + 1):
        t = 2 * math.pi * num_revs * i / total_points
        x0 = diff * math.cos(t) + d * math.cos(ratio * t)
        y0 = diff * math.sin(t) - d * math.sin(ratio * t)
        # Scale
        x0 *= scale
        y0 *= scale
        # Rotate
        x = cx + x0 * math.cos(rot) - y0 * math.sin(rot)
        y = cy + x0 * math.sin(rot) + y0 * math.cos(rot)
        pts.append((x, y))
    return pts


def compute_num_revolutions(R, r):
    g = math.gcd(int(R), int(r))
    return int(r) // g


def compute_num_petals(R, r):
    g = math.gcd(int(R), int(r))
    return int(R) // g


def seg_length(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


# ─── G-code Generator ───────────────────────────────────────────────────────

class NestedSpirographGenerator:
    def __init__(self, *, R, r, d, scales, num_layers, twist_deg,
                 layer_height, first_z, pts_per_rev, cx, cy,
                 print_speed, travel_speed, e_mult, retract, z_hop):
        self.R = R
        self.r = r
        self.d = d
        self.scales = scales  # list of scale factors [outer, middle, inner]
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
        self.num_petals = compute_num_petals(R, r)
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
        max_d = ((self.R - self.r) + self.d) * self.scales[0] * 2
        total_height = self.first_z + (self.num_layers - 1) * self.layer_height
        total_twist = self.twist_deg * (self.num_layers - 1)
        self._emit("; 3-Color Nested Spirograph — Food Printing G-code")
        self._emit("; Multi-material: 3 syringe colors per layer")
        self._emit(";")
        for i, (label, desc) in enumerate(MATERIALS):
            scale_pct = self.scales[i] * 100 if i < len(self.scales) else 0
            self._emit(f"; Material {label}: {desc} (scale {scale_pct:.0f}%)")
        self._emit(";")
        self._emit(f"; Hypotrochoid: R={self.R:.0f}, r={self.r:.0f}, d={self.d:.0f}")
        self._emit(f"; Petals: {self.num_petals}  |  Revolutions: {self.num_revs}")
        self._emit(f"; Outer ring diameter: ~{max_d:.0f}mm")
        self._emit(f"; Points per ring: {self.total_points}")
        self._emit(f";")
        self._emit(f"; Layers: {self.num_layers}")
        self._emit(f"; Rings per layer: {len(self.scales)}")
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
        self._emit(f"; ╔══════════════════════════════════════════════╗")
        self._emit(f"; ║  LAYER {layer_idx + 1}/{self.num_layers} "
                    f"(Z={z:.1f}mm, θ={rotation:.1f}°)             ║")
        self._emit(f"; ╚══════════════════════════════════════════════╝")

        ring_names = ["outer", "middle", "inner"]

        for ring_idx, scale in enumerate(self.scales):
            mat_label = MATERIALS[ring_idx][0]
            mat_desc = MATERIALS[ring_idx][1]
            ring_name = ring_names[ring_idx] if ring_idx < len(ring_names) else f"ring-{ring_idx}"

            # Material switch (pause for syringe swap)
            if ring_idx == 0 and layer_idx == 0:
                # First ring of first layer — just announce
                self._emit("")
                self._emit(f"; >>> SYRINGE: Material {mat_label} — {mat_desc} <<<")
            elif ring_idx == 0 and layer_idx > 0:
                # First ring of subsequent layers — switch back to A
                self._emit("")
                self._emit(f"; *** MATERIAL SWITCH → {mat_label} ***")
                self._emit(f"; >>> PAUSE: Load syringe {mat_label} — {mat_desc} <<<")
                self._emit(f"M0               ; Pause for syringe swap")
            else:
                # Switching between rings within a layer
                self._emit("")
                self._emit(f"; *** MATERIAL SWITCH → {mat_label} ***")
                self._emit(f"; >>> PAUSE: Load syringe {mat_label} — {mat_desc} <<<")
                self._emit(f"M0               ; Pause for syringe swap")

            self._emit("")
            self._emit(f"; --- {ring_name} ring (scale {scale*100:.0f}%, "
                        f"Material {mat_label}) ---")

            # Generate the spirograph curve
            points = hypotrochoid_points(
                self.R, self.r, self.d,
                self.num_revs, self.total_points,
                self.cx, self.cy,
                rotation_deg=rotation,
                scale=scale,
            )

            # Travel to first point
            x0, y0 = points[0]
            self._emit(f"G1 Z{z + self.z_hop:.2f} F600   ; Z-hop")
            self._emit(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Travel to {ring_name} start")
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
        description="Generate 3-color nested spirograph G-code for food printing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Prints 3 concentric spirograph rings per layer in 3 different materials.
The printer pauses (M0) between each ring for syringe swapping.

examples:
  %(prog)s                              Default: 3 layers, 5-petal pattern
  %(prog)s --layers 5 --twist 8         5 layers, 8° twist
  %(prog)s --scales 1.0 0.75 0.5        Custom ring scale ratios
  %(prog)s --R 28 --r 8 --d 6           7-petal variant
""",
    )
    parser.add_argument("--R", type=float, default=BASE_R,
                        help=f"Fixed circle radius (default: {BASE_R})")
    parser.add_argument("--r", type=float, default=BASE_r,
                        help=f"Rolling circle radius (default: {BASE_r})")
    parser.add_argument("--d", type=float, default=BASE_d,
                        help=f"Pen offset (default: {BASE_d})")
    parser.add_argument("--scales", type=float, nargs=3,
                        default=[SCALE_OUTER, SCALE_MIDDLE, SCALE_INNER],
                        metavar=("OUTER", "MID", "INNER"),
                        help=f"Scale factors for outer/mid/inner rings "
                             f"(default: {SCALE_OUTER} {SCALE_MIDDLE} {SCALE_INNER})")
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

    gen = NestedSpirographGenerator(
        R=args.R, r=args.r, d=args.d,
        scales=args.scales,
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
        out_path = os.path.join(script_dir, "di2256_spirograph_v2.gcode")

    with open(out_path, "w") as f:
        f.write(gcode)

    petals = compute_num_petals(args.R, args.r)
    revs = compute_num_revolutions(args.R, args.r)
    total_height = FIRST_Z + (args.layers - 1) * args.layer_height
    total_twist = args.twist * (args.layers - 1)
    swaps = args.layers * len(args.scales) - 1

    print(f"✓ Generated: {out_path}")
    print(f"  {petals} petals, {revs} revolutions per ring")
    print(f"  {len(args.scales)} rings per layer × {args.layers} layers")
    print(f"  Scales: {' / '.join(f'{s*100:.0f}%' for s in args.scales)}")
    print(f"  Height: {total_height:.1f}mm, twist: {total_twist:.1f}° total")
    print(f"  Material swaps: {swaps} (M0 pauses)")


if __name__ == "__main__":
    main()
