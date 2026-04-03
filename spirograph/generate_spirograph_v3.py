#!/usr/bin/env python3
"""
generate_spirograph_v3.py — Generate G-code for a 3-color flower spirograph.

Prints a flower pattern using rose curves (rhodonea) on each layer:
  - Outer petals  (Material A — teal)
  - Inner petals  (Material B — pink, rotated to interleave)
  - Center circle (Material C — purple)

Each layer prints all 3 elements, with M0 pause for syringe swaps.
Multiple layers can be stacked with a twist for a 3D flower tower.

Usage:
    python generate_spirograph_v3.py
    python generate_spirograph_v3.py --petals 7 --layers 5
    python generate_spirograph_v3.py --help
"""

import argparse
import math
import os
import sys

# ─── Flower / Rose Curve Defaults ─────────────────────────────────────────

PETAL_COUNT     = 5          # number of petals per rose curve
PETAL_AMPLITUDE = 26.0       # max petal radius (mm) → ~52mm diameter

# 3 concentric elements
SCALE_OUTER     = 1.0        # outer petals at full size (~52mm dia)
SCALE_MIDDLE    = 0.60       # inner petals at 60% (~31mm dia)
CENTER_RADIUS   = 5.0        # center circle radius (mm)

# 3D stacking
NUM_LAYERS      = 3          # layers (kept small to limit syringe swaps)
TWIST_LAYER     = 12.0       # degrees to rotate the whole pattern per layer
LAYER_HEIGHT    = 2.0
FIRST_Z         = 3.0        # matches twisted triangle v2 plate height

# Resolution
POINTS_PER_PETAL = 60        # points per petal for rose curve
CIRCLE_POINTS    = 120       # points for center circle

# Print bed center
CENTER_X        = 100.0
CENTER_Y        = 100.0

# Print parameters
PRINT_SPEED     = 300
TRAVEL_SPEED    = 1200
E_MULT          = 0.10
RETRACT         = 1.5
Z_HOP           = 1.0

# Material labels
MATERIALS = [
    ("A", "Cream Cheese + blue dye (teal)"),
    ("B", "Cream Cheese + beet powder (pink)"),
    ("C", "Cream Cheese + ube extract (purple)"),
]


# ─── Flower Math ──────────────────────────────────────────────────────────

def rose_curve_points(k, amplitude, total_points, cx, cy, rotation_deg, scale):
    """Generate points along a rose curve: r = amplitude * cos(k * theta).

    For odd k: traces k petals over [0, π].
    For even k: traces 2k petals over [0, 2π].
    """
    rot = math.radians(rotation_deg)
    pts = []

    # Odd k completes in π, even k needs 2π
    if k % 2 == 1:
        t_max = math.pi
    else:
        t_max = 2 * math.pi

    for i in range(total_points + 1):
        t = t_max * i / total_points
        r = amplitude * math.cos(k * t) * scale

        x0 = r * math.cos(t)
        y0 = r * math.sin(t)

        # Rotate
        x = cx + x0 * math.cos(rot) - y0 * math.sin(rot)
        y = cy + x0 * math.sin(rot) + y0 * math.cos(rot)
        pts.append((x, y))
    return pts


def circle_points(radius, total_points, cx, cy, rotation_deg=0):
    """Generate points along a circle."""
    rot = math.radians(rotation_deg)
    pts = []
    for i in range(total_points + 1):
        t = 2 * math.pi * i / total_points
        x0 = radius * math.cos(t)
        y0 = radius * math.sin(t)
        x = cx + x0 * math.cos(rot) - y0 * math.sin(rot)
        y = cy + x0 * math.sin(rot) + y0 * math.cos(rot)
        pts.append((x, y))
    return pts


def seg_length(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


# ─── G-code Generator ───────────────────────────────────────────────────────

class FlowerSpirographGenerator:
    def __init__(self, *, petal_count, amplitude, scales, center_radius,
                 rotation_offset, num_layers, twist_deg,
                 layer_height, first_z, pts_per_petal, circle_pts,
                 cx, cy, print_speed, travel_speed, e_mult, retract, z_hop):
        self.petal_count = petal_count
        self.amplitude = amplitude
        self.scales = scales          # [outer_scale, middle_scale]
        self.center_radius = center_radius
        self.rotation_offset = rotation_offset
        self.num_layers = num_layers
        self.twist_deg = twist_deg
        self.layer_height = layer_height
        self.first_z = first_z
        self.pts_per_petal = pts_per_petal
        self.circle_pts = circle_pts
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

        # Total points for the rose curve
        self.total_rose_points = self.pts_per_petal * self.petal_count

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
        max_d = self.amplitude * self.scales[0] * 2
        inner_d = self.amplitude * self.scales[1] * 2
        total_height = self.first_z + (self.num_layers - 1) * self.layer_height
        total_twist = self.twist_deg * (self.num_layers - 1)
        self._emit("; 3-Color Flower Spirograph — Food Printing G-code")
        self._emit("; Rose curve (rhodonea) flower pattern")
        self._emit("; Multi-material: 3 syringe colors per layer")
        self._emit(";")
        self._emit(f"; Material A: {MATERIALS[0][1]} (outer petals, scale {self.scales[0]*100:.0f}%)")
        self._emit(f"; Material B: {MATERIALS[1][1]} (inner petals, scale {self.scales[1]*100:.0f}%)")
        self._emit(f"; Material C: {MATERIALS[2][1]} (center circle)")
        self._emit(";")
        self._emit(f"; Pattern: {self.petal_count}-petal rose curve r = a·cos({self.petal_count}θ)")
        self._emit(f"; Outer petal diameter: ~{max_d:.0f}mm")
        self._emit(f"; Inner petal diameter: ~{inner_d:.0f}mm")
        self._emit(f"; Center circle diameter: ~{self.center_radius * 2:.0f}mm")
        self._emit(f"; Inner petals rotated {self.rotation_offset:.0f}° to interleave")
        self._emit(f";")
        self._emit(f"; Layers: {self.num_layers}")
        self._emit(f"; Elements per layer: 3 (outer petals + inner petals + center)")
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

        ring_names = ["outer petals", "inner petals", "center circle"]

        for ring_idx in range(3):
            mat_label = MATERIALS[ring_idx][0]
            mat_desc = MATERIALS[ring_idx][1]
            ring_name = ring_names[ring_idx]

            # Material switch (pause for syringe swap)
            if ring_idx == 0 and layer_idx == 0:
                self._emit("")
                self._emit(f"; >>> SYRINGE: Material {mat_label} — {mat_desc} <<<")
            elif ring_idx == 0 and layer_idx > 0:
                self._emit("")
                self._emit(f"; *** MATERIAL SWITCH → {mat_label} ***")
                self._emit(f"; >>> PAUSE: Load syringe {mat_label} — {mat_desc} <<<")
                self._emit(f"M0               ; Pause for syringe swap")
            else:
                self._emit("")
                self._emit(f"; *** MATERIAL SWITCH → {mat_label} ***")
                self._emit(f"; >>> PAUSE: Load syringe {mat_label} — {mat_desc} <<<")
                self._emit(f"M0               ; Pause for syringe swap")

            self._emit("")
            self._emit(f"; --- {ring_name} (Material {mat_label}) ---")

            # Generate the appropriate curve
            if ring_idx == 0:
                # Outer petals: rose curve at full scale
                points = rose_curve_points(
                    self.petal_count, self.amplitude,
                    self.total_rose_points,
                    self.cx, self.cy,
                    rotation_deg=rotation,
                    scale=self.scales[0],
                )
            elif ring_idx == 1:
                # Inner petals: rose curve, smaller, rotated to interleave
                points = rose_curve_points(
                    self.petal_count, self.amplitude,
                    self.total_rose_points,
                    self.cx, self.cy,
                    rotation_deg=rotation + self.rotation_offset,
                    scale=self.scales[1],
                )
            else:
                # Center circle
                points = circle_points(
                    self.center_radius, self.circle_pts,
                    self.cx, self.cy,
                    rotation_deg=rotation,
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
        description="Generate 3-color flower spirograph G-code for food printing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Prints a flower pattern using rose curves (rhodonea):
  - Outer petals (large rose curve)
  - Inner petals (smaller, rotated rose curve to interleave)
  - Center circle
The printer pauses (M0) between each element for syringe swapping.

examples:
  %(prog)s                              Default: 5-petal flower, 3 layers
  %(prog)s --petals 7 --layers 5        7-petal flower, 5 layers
  %(prog)s --twist 15                   More twist between layers
  %(prog)s --amplitude 30               Larger flower
""",
    )
    parser.add_argument("--petals", type=int, default=PETAL_COUNT,
                        help=f"Number of petals (default: {PETAL_COUNT})")
    parser.add_argument("--amplitude", type=float, default=PETAL_AMPLITUDE,
                        help=f"Max petal radius in mm (default: {PETAL_AMPLITUDE})")
    parser.add_argument("--scales", type=float, nargs=2,
                        default=[SCALE_OUTER, SCALE_MIDDLE],
                        metavar=("OUTER", "INNER"),
                        help=f"Scale factors for outer/inner petals "
                             f"(default: {SCALE_OUTER} {SCALE_MIDDLE})")
    parser.add_argument("--center-radius", type=float, default=CENTER_RADIUS,
                        help=f"Center circle radius in mm (default: {CENTER_RADIUS})")
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
    parser.add_argument("--resolution", type=int, default=POINTS_PER_PETAL,
                        help=f"Points per petal (default: {POINTS_PER_PETAL})")
    parser.add_argument("-o", "--output", default=None,
                        help="Output file path")

    args = parser.parse_args()

    # Half-petal rotation to interleave inner petals between outer ones
    rotation_offset = 360.0 / (args.petals * 2)

    gen = FlowerSpirographGenerator(
        petal_count=args.petals,
        amplitude=args.amplitude,
        scales=args.scales,
        center_radius=args.center_radius,
        rotation_offset=rotation_offset,
        num_layers=args.layers,
        twist_deg=args.twist,
        layer_height=args.layer_height,
        first_z=FIRST_Z,
        pts_per_petal=args.resolution,
        circle_pts=CIRCLE_POINTS,
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
        out_path = os.path.join(script_dir, "di2256_spirograph_v3.gcode")

    with open(out_path, "w") as f:
        f.write(gcode)

    total_height = FIRST_Z + (args.layers - 1) * args.layer_height
    total_twist = args.twist * (args.layers - 1)
    swaps = args.layers * 3 - 1

    print(f"✓ Generated: {out_path}")
    print(f"  {args.petals}-petal flower pattern")
    print(f"  3 elements per layer × {args.layers} layers")
    print(f"  Outer petal radius: {args.amplitude * args.scales[0]:.1f}mm")
    print(f"  Inner petal radius: {args.amplitude * args.scales[1]:.1f}mm")
    print(f"  Center circle radius: {args.center_radius:.1f}mm")
    print(f"  Height: {total_height:.1f}mm, twist: {total_twist:.1f}° total")
    print(f"  Material swaps: {swaps} (M0 pauses)")


if __name__ == "__main__":
    main()
