#!/usr/bin/env python3
"""
generate_twisted_triangle.py — Generate G-code for a twisted-triangle pyramid.

Structure:
  - Each "step" prints the SAME triangle TWICE (two layers stacked on top
    of each other at the same size and angle) for rigidity / thickness.
  - Between steps, the triangle ROTATES by a fixed angle and SHRINKS.
  - This builds a twisted, tapered tower.

Material: Peanut Butter (stiffer paste — different from cream cheese in Part 1)
  Recipe: Smooth peanut butter mixed with ~10% powdered sugar for stiffness.
          Warm slightly (30°C) before loading into syringe.

Usage:
    python generate_twisted_triangle.py
    python generate_twisted_triangle.py --steps 8 --twist 15
    python generate_twisted_triangle.py --help
"""

import argparse
import math
import os
import sys

# ─── Defaults ────────────────────────────────────────────────────────────────

NUM_STEPS        = 6         # number of distinct triangle sizes
LAYERS_PER_STEP  = 2         # print each triangle twice for rigidity
BASE_RADIUS      = 20.0      # circumradius of the triangle at step 1 (mm)
MIN_RADIUS       = 6.0       # circumradius at the final step (mm)
TWIST_PER_STEP   = 15.0      # rotation between steps (degrees)

# Print bed center (for ~200mm bed)
CENTER_X         = 100.0
CENTER_Y         = 100.0

# Print parameters (tuned for peanut butter / stiff paste)
LAYER_HEIGHT     = 2.0       # mm per layer
FIRST_LAYER_Z    = 9.0       # Z of the very first layer (raised for bed clearance)
PRINT_SPEED      = 300       # mm/min for extrusion moves
TRAVEL_SPEED     = 1200      # mm/min for non-extrusion moves
EXTRUSION_MULT   = 0.06      # E mm per mm of XY travel (reduced for thinner lines)
RETRACT_DIST     = 1.5       # retraction to reduce ooze between layers
Z_HOP            = 1.0       # Z hop during travel moves


# ─── Helpers ─────────────────────────────────────────────────────────────────

def triangle_vertices(cx, cy, radius, angle_offset_deg):
    """Return 3 vertices of an equilateral triangle centered at (cx, cy).
    angle_offset_deg rotates the whole triangle."""
    verts = []
    for i in range(3):
        a = math.radians(angle_offset_deg + i * 120)
        verts.append((
            cx + radius * math.cos(a),
            cy + radius * math.sin(a),
        ))
    return verts


def seg_length(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


# ─── G-code Generator ───────────────────────────────────────────────────────

class TwistedTriangleGenerator:
    def __init__(self, *, num_steps, layers_per_step, base_radius, min_radius,
                 twist_deg, layer_height, first_z, center_x, center_y,
                 print_speed, travel_speed, extrusion_mult, retract, z_hop):
        self.num_steps = num_steps
        self.layers_per_step = layers_per_step
        self.base_radius = base_radius
        self.min_radius = min_radius
        self.twist_deg = twist_deg
        self.layer_height = layer_height
        self.first_z = first_z
        self.cx = center_x
        self.cy = center_y
        self.print_speed = print_speed
        self.travel_speed = travel_speed
        self.e_mult = extrusion_mult
        self.retract = retract
        self.z_hop = z_hop

        self.lines = []
        self.e_total = 0.0
        self.current_z = 0.0
        self.layer_num = 0   # running layer counter
        self._retracted = False  # track retraction state

    def generate(self) -> str:
        self._header()
        self._init_block()

        for step in range(self.num_steps):
            self._generate_step(step)

        self._finish_block()
        return "\n".join(self.lines) + "\n"

    # ── internals ──

    def _emit(self, line):
        self.lines.append(line)

    def _header(self):
        total_layers = self.num_steps * self.layers_per_step
        total_height = self.first_z + (total_layers - 1) * self.layer_height
        total_twist = self.twist_deg * (self.num_steps - 1)
        self._emit("; Twisted Triangle Pyramid — Food Printing G-code")
        self._emit("; Material: Peanut Butter (stiff paste)")
        self._emit(";")
        self._emit("; Recipe: Smooth peanut butter + ~10% powdered sugar")
        self._emit(";         Warm to ~30°C before loading into syringe.")
        self._emit(";")
        self._emit(f"; Steps: {self.num_steps} (each triangle printed {self.layers_per_step}× for rigidity)")
        self._emit(f"; Total layers: {total_layers}")
        self._emit(f"; Base radius: {self.base_radius:.1f}mm → Top radius: {self.min_radius:.1f}mm")
        self._emit(f"; Twist per step: {self.twist_deg:.1f}° (total: {total_twist:.1f}°)")
        self._emit(f"; Layer height: {self.layer_height:.1f}mm")
        self._emit(f"; Total height: {total_height:.1f}mm")
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
        # Last layer already retracted, just raise and go home
        final_z = self.current_z + 20
        self._emit(f"G1 Z{final_z:.1f} F600      ; Raise nozzle clear")
        self._emit(f"G1 X0 Y0 F{self.travel_speed}   ; Move to home")
        self._emit("M84              ; Disable motors")
        self._emit("")
        self._emit("; === END ===")

    def _generate_step(self, step_idx):
        """Generate one 'step' = same triangle printed layers_per_step times."""
        # Radius for this step (linear interpolation from base to min)
        t = step_idx / max(self.num_steps - 1, 1)
        radius = self.base_radius * (1 - t) + self.min_radius * t

        # Rotation angle for this step
        angle = step_idx * self.twist_deg

        # Compute the vertices once — same for all layers in this step
        verts = triangle_vertices(self.cx, self.cy, radius, angle)

        self._emit("")
        self._emit(f"; ──── STEP {step_idx + 1}/{self.num_steps} "
                    f"(R={radius:.1f}mm, θ={angle:.1f}°) "
                    f"× {self.layers_per_step} layers ────")

        for rep in range(self.layers_per_step):
            z = self.first_z + self.layer_num * self.layer_height
            self.current_z = z
            self.layer_num += 1

            self._emit("")
            self._emit(f"; --- Layer {self.layer_num} "
                        f"(Z={z:.1f}mm, step {step_idx + 1} rep {rep + 1}/{self.layers_per_step}) ---")

            # Travel to the first vertex of the triangle
            x0, y0 = verts[0]
            self._emit(f"G1 Z{z + self.z_hop:.2f} F600   ; Z-hop")
            self._emit(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Travel to start")
            self._emit(f"G1 Z{z:.2f} F300   ; Lower to layer height")

            # Prime: push material back to the nozzle tip before extruding
            if self._retracted:
                self.e_total += self.retract
                self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}   ; Prime")
                self._retracted = False

            # Draw the three edges of the triangle (closed loop)
            edge_labels = ["edge 1/3", "edge 2/3", "edge 3/3 (close)"]
            for i in range(3):
                p_end = verts[(i + 1) % 3]
                p_start = verts[i]
                d = seg_length(p_start, p_end)
                self.e_total += d * self.e_mult
                self._emit(f"G1 X{p_end[0]:.3f} Y{p_end[1]:.3f} "
                            f"E{self.e_total:.4f} F{self.print_speed}"
                            f"   ; {edge_labels[i]}")

            # Retract after each triangle to reduce stringing
            self.e_total -= self.retract
            self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}   ; Retract")
            self._retracted = True


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate twisted-triangle pyramid G-code for food printing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Structure:
  Each triangle is printed TWICE (stacked) for rigidity, then the next
  step rotates and shrinks the triangle. This builds a twisted tower.

examples:
  %(prog)s                             Default 6-step pyramid (12 layers)
  %(prog)s --steps 8 --twist 12        8 steps, 12° twist between steps
  %(prog)s --reps 3                    Print each triangle 3× for extra rigidity
  %(prog)s --radius 25 --min-radius 5  Larger base, smaller top
""",
    )
    parser.add_argument("--steps", type=int, default=NUM_STEPS,
                        help=f"Number of distinct triangle sizes (default: {NUM_STEPS})")
    parser.add_argument("--reps", type=int, default=LAYERS_PER_STEP,
                        help=f"Layers per step — how many times each triangle is printed (default: {LAYERS_PER_STEP})")
    parser.add_argument("--radius", type=float, default=BASE_RADIUS,
                        help=f"Base circumradius in mm (default: {BASE_RADIUS})")
    parser.add_argument("--min-radius", type=float, default=MIN_RADIUS,
                        help=f"Top circumradius in mm (default: {MIN_RADIUS})")
    parser.add_argument("--twist", type=float, default=TWIST_PER_STEP,
                        help=f"Rotation between steps in degrees (default: {TWIST_PER_STEP})")
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT,
                        help=f"Layer height in mm (default: {LAYER_HEIGHT})")
    parser.add_argument("--speed", type=int, default=PRINT_SPEED,
                        help=f"Print speed in mm/min (default: {PRINT_SPEED})")
    parser.add_argument("--e-mult", type=float, default=EXTRUSION_MULT,
                        help=f"Extrusion multiplier mm/mm (default: {EXTRUSION_MULT})")
    parser.add_argument("-o", "--output", default=None,
                        help="Output file path (default: auto-named in script dir)")

    args = parser.parse_args()

    gen = TwistedTriangleGenerator(
        num_steps=args.steps,
        layers_per_step=args.reps,
        base_radius=args.radius,
        min_radius=args.min_radius,
        twist_deg=args.twist,
        layer_height=args.layer_height,
        first_z=FIRST_LAYER_Z,
        center_x=CENTER_X,
        center_y=CENTER_Y,
        print_speed=args.speed,
        travel_speed=TRAVEL_SPEED,
        extrusion_mult=args.e_mult,
        retract=RETRACT_DIST,
        z_hop=Z_HOP,
    )

    gcode = gen.generate()

    if args.output:
        out_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(script_dir, "di2256_twisted_triangle_v1.gcode")

    with open(out_path, "w") as f:
        f.write(gcode)

    total_layers = args.steps * args.reps
    total_height = FIRST_LAYER_Z + (total_layers - 1) * args.layer_height
    total_twist = args.twist * (args.steps - 1)

    print(f"✓ Generated: {out_path}")
    print(f"  {args.steps} steps × {args.reps} layers = {total_layers} layers total")
    print(f"  Height: {total_height:.1f}mm")
    print(f"  Base R={args.radius:.1f}mm → Top R={args.min_radius:.1f}mm")
    print(f"  Twist: {args.twist:.1f}°/step × {args.steps - 1} = {total_twist:.1f}° total")


if __name__ == "__main__":
    main()
