#!/usr/bin/env python3
"""
generate_diane_fort.py — Generate a cup-shaped G-code structure.

CUP STRUCTURE
─────────────
  Outline file  (di2256_fort_outline.gcode):
    Layer 1  → solid concentric-ring BASE (fills the whole circle)
    Layers 2+ → outer circle WALL only (builds up the cup sides)

  Fill file     (di2256_fort_fill.gcode):
    Layer 2 only → concentric rings inside the cup walls
    (use with a second syringe / second material — e.g. jam)

Usage:
    python generate_diane_fort.py
    python generate_diane_fort.py --wall-layers 8 --tower-radius 26
    python generate_diane_fort.py --first-z 2.5 --ring-step 3.5
"""

import argparse
import math
import os
import sys


# ─── Defaults ────────────────────────────────────────────────────────────────

WALL_LAYERS       = 8          # how many circular-wall layers (above the base)
LAYER_HEIGHT      = 1.0        # mm per wall layer (shorter steps)
FIRST_LAYER_Z     = 5.5        # Z of the solid base layer (+3mm from previous 2.5)

CENTER_X          = 100.0
CENTER_Y          = 100.0

# Match spirograph v4 outer diameter of 52 mm.
TOWER_RADIUS      = 26.0
RING_STEP         = 2.0        # spacing between concentric fill rings (mm) — tight, no gaps
INNER_MARGIN      = 3.0        # gap between outer wall and innermost fill ring (mm)
POINTS_PER_RING   = 72         # polygon resolution per circle

PRINT_SPEED       = 800        # mm/min — faster = thinner deposit, less blobbing
TRAVEL_SPEED      = 1200
EXTRUSION_MULT    = 0.025      # E mm per mm of XY travel (tuned thin)
FIRST_RING_REPS   = 3          # repeat the innermost ring this many times to prime/push down
RETRACT_DIST      = 1.5
Z_HOP             = 1.0

OUTLINE_FILE      = "di2256_fort_outline.gcode"
FILL_FILE         = "di2256_fort_fill.gcode"


# ─── Geometry Helpers ────────────────────────────────────────────────────────

def circle_ring(cx, cy, radius, points_per_ring):
    """Return a closed list of (x, y) points forming a circle."""
    pts = []
    for i in range(points_per_ring + 1):
        theta = 2.0 * math.pi * i / points_per_ring
        pts.append((cx + radius * math.cos(theta),
                    cy + radius * math.sin(theta)))
    return pts


def dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


# ─── G-code Generator ────────────────────────────────────────────────────────

class CupGenerator:
    def __init__(
        self,
        *,
        wall_layers,
        layer_height,
        first_z,
        cx,
        cy,
        tower_radius,
        ring_step,
        inner_margin,
        points_per_ring,
        print_speed,
        travel_speed,
        extrusion_mult,
        retract,
        z_hop,
        first_ring_reps,
    ):
        self.wall_layers      = wall_layers
        self.layer_height     = layer_height
        self.first_z          = first_z
        self.cx               = cx
        self.cy               = cy
        self.tower_radius     = tower_radius
        self.ring_step        = ring_step
        self.inner_margin     = inner_margin
        self.points_per_ring  = points_per_ring
        self.print_speed      = print_speed
        self.travel_speed     = travel_speed
        self.e_mult           = extrusion_mult
        self.retract          = retract
        self.z_hop            = z_hop
        self.first_ring_reps  = first_ring_reps

    # ── layer Z helpers ──

    def _base_z(self):
        return self.first_z

    def _wall_z(self, wall_idx):
        """wall_idx 0 = first wall layer directly above the base."""
        return self.first_z + (wall_idx + 1) * self.layer_height

    # ── low-level emitters ──

    def _header(self, mode, extra_notes=""):
        lines = []
        lines.append(f"; Diane Fort — Cup {mode} G-code")
        lines.append("; Food Printing assignment")
        lines.append(";")
        lines.append("; CUP STRUCTURE:")
        lines.append(";   Outline: solid base (layer 1) + circular wall (layers 2+)")
        lines.append(";   Fill   : concentric rings inside cup (second material)")
        lines.append(";")
        lines.append(f"; Wall layers: {self.wall_layers}")
        lines.append(f"; Layer height: {self.layer_height:.1f} mm")
        lines.append(f"; Base Z: {self._base_z():.2f} mm")
        wall_top = self._wall_z(self.wall_layers - 1) if self.wall_layers else self._base_z()
        lines.append(f"; Wall top Z: {wall_top:.2f} mm")
        lines.append(f"; Radius: {self.tower_radius:.1f} mm  (diameter {self.tower_radius*2:.1f} mm)")
        lines.append(f"; Center: ({self.cx:.0f}, {self.cy:.0f})")
        lines.append(f"; Print speed: {self.print_speed} mm/min")
        lines.append(f"; Extrusion mult: {self.e_mult}")
        if extra_notes:
            lines.append(f"; {extra_notes}")
        lines.append("")
        lines.append("; === INITIALIZATION ===")
        lines.append("G21              ; Set units to millimeters")
        lines.append("G90              ; Absolute positioning")
        lines.append("M82              ; Absolute extrusion mode")
        lines.append("G28              ; Home all axes")
        lines.append("")
        return lines

    def _finish(self, lines, current_z):
        lines.append("")
        lines.append("; === FINISH ===")
        lines.append(f"G1 Z{current_z + 20:.1f} F600      ; Raise nozzle clear")
        lines.append(f"G1 X0 Y0 F{self.travel_speed}   ; Move to home position")
        lines.append("M84              ; Disable motors")
        lines.append("")
        lines.append("; === END ===")

    def _emit_path(self, lines, points, z, e_total, retracted, label):
        """Travel to start of path, lower, prime if needed, extrude, retract."""
        x0, y0 = points[0]
        lines.append(f"G1 Z{z + self.z_hop:.2f} F600   ; Z-hop")
        lines.append(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Travel → {label}")
        lines.append(f"G1 Z{z:.2f} F300   ; Lower to Z")

        if retracted:
            e_total += self.retract
            lines.append(f"G1 E{e_total:.4f} F{self.travel_speed}   ; Prime")
            retracted = False

        for i in range(1, len(points)):
            d = dist(points[i - 1], points[i])
            if d < 0.001:
                continue
            e_total += d * self.e_mult
            lines.append(
                f"G1 X{points[i][0]:.3f} Y{points[i][1]:.3f} "
                f"E{e_total:.4f} F{self.print_speed}"
            )

        e_total -= self.retract
        lines.append(f"G1 E{e_total:.4f} F{self.travel_speed}   ; Retract")
        return e_total, True

    def _emit_concentric_fill(self, lines, z, e_total, retracted, max_radius, label_prefix):
        """Print concentric rings from center outward (small → large radius).
        The innermost ring is repeated self.first_ring_reps times to prime/push material down."""
        # Build list of radii from innermost to outermost
        radii = []
        r = self.ring_step
        while r <= max_radius:
            radii.append(r)
            r += self.ring_step
        # If max_radius itself isn't hit exactly, add it as the outer wall ring
        if not radii or radii[-1] < max_radius:
            radii.append(max_radius)

        for ring_idx, radius in enumerate(radii):
            reps = self.first_ring_reps if ring_idx == 0 else 1
            pts = circle_ring(self.cx, self.cy, radius, self.points_per_ring)
            if ring_idx % 2 == 1:          # alternate direction to reduce travel
                pts = list(reversed(pts))
            for rep in range(reps):
                rep_label = f"{label_prefix} ring {ring_idx + 1} (r={radius:.1f}mm)"
                if reps > 1:
                    rep_label += f" rep {rep + 1}/{reps}"
                e_total, retracted = self._emit_path(
                    lines, pts, z, e_total, retracted, rep_label
                )
        return e_total, retracted

    # ── public generators ──

    def generate_outline(self):
        """
        Layer 1 : solid concentric-ring BASE (fills the full circle)
        Layers 2+: outer circle WALL only
        """
        lines = self._header(
            "Outline",
            extra_notes="Layer 1=base fill  |  Layers 2+= wall circle"
        )
        e_total  = 0.0
        retracted = False
        current_z = self._base_z()

        # ── LAYER 1: solid base ──────────────────────────────────────────────
        z = self._base_z()
        lines.append(f"; === LAYER 1 — SOLID BASE  (Z={z:.2f} mm) ===")
        e_total, retracted = self._emit_concentric_fill(
            lines, z, e_total, retracted,
            max_radius=self.tower_radius,   # fill the entire circle
            label_prefix="base"
        )

        # ── LAYERS 2+: circular wall ─────────────────────────────────────────
        for w in range(self.wall_layers):
            z = self._wall_z(w)
            current_z = z
            pts = circle_ring(self.cx, self.cy, self.tower_radius, self.points_per_ring)
            lines.append("")
            lines.append(f"; === LAYER {w + 2} — WALL  (Z={z:.2f} mm) ===")
            e_total, retracted = self._emit_path(
                lines, pts, z, e_total, retracted, "wall circle"
            )

        self._finish(lines, current_z)
        return "\n".join(lines) + "\n"

    def generate_fill(self):
        """
        Single layer of concentric rings inside the cup walls.
        Print this with a second material (e.g. jam) after the outline.
        The fill Z is one layer above the base so it sits inside the cup.
        """
        fill_z = self._wall_z(0)   # same Z as the first wall layer
        max_r  = self.tower_radius - self.inner_margin

        lines = self._header(
            "Fill (second material)",
            extra_notes=f"Single fill layer at Z={fill_z:.2f} mm inside the cup"
        )
        e_total  = 0.0
        retracted = False

        lines.append(f"; === FILL LAYER — INSIDE CUP  (Z={fill_z:.2f} mm) ===")
        e_total, retracted = self._emit_concentric_fill(
            lines, fill_z, e_total, retracted,
            max_radius=max_r,
            label_prefix="fill"
        )

        self._finish(lines, fill_z)
        return "\n".join(lines) + "\n"


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a cup-shaped G-code (solid base + circular wall).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                             Default 6-layer wall cup
  %(prog)s --wall-layers 4             Shorter cup (4 wall layers)
  %(prog)s --tower-radius 30           Wider cup
  %(prog)s --first-z 3.0 --ring-step 3.5
""",
    )
    parser.add_argument("--wall-layers", type=int, default=WALL_LAYERS,
                        help=f"Number of circular wall layers above the base (default: {WALL_LAYERS})")
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT,
                        help=f"Layer height in mm (default: {LAYER_HEIGHT})")
    parser.add_argument("--first-z", type=float, default=FIRST_LAYER_Z,
                        help=f"Z height of the base layer in mm (default: {FIRST_LAYER_Z})")
    parser.add_argument("--tower-radius", type=float, default=TOWER_RADIUS,
                        help=f"Cup radius in mm (default: {TOWER_RADIUS})")
    parser.add_argument("--ring-step", type=float, default=RING_STEP,
                        help=f"Spacing between base fill rings in mm (default: {RING_STEP})")
    parser.add_argument("--inner-margin", type=float, default=INNER_MARGIN,
                        help=f"Gap between cup wall and fill rings in mm (default: {INNER_MARGIN})")
    args = parser.parse_args()

    if args.wall_layers < 0:
        print("error: --wall-layers must be >= 0", file=sys.stderr)
        sys.exit(2)
    if args.tower_radius <= 0:
        print("error: --tower-radius must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.ring_step <= 0:
        print("error: --ring-step must be > 0", file=sys.stderr)
        sys.exit(2)

    gen = CupGenerator(
        wall_layers=args.wall_layers,
        layer_height=args.layer_height,
        first_z=args.first_z,
        cx=CENTER_X,
        cy=CENTER_Y,
        tower_radius=args.tower_radius,
        ring_step=args.ring_step,
        inner_margin=args.inner_margin,
        points_per_ring=POINTS_PER_RING,
        print_speed=PRINT_SPEED,
        travel_speed=TRAVEL_SPEED,
        extrusion_mult=EXTRUSION_MULT,
        retract=RETRACT_DIST,
        first_ring_reps=FIRST_RING_REPS,
        z_hop=Z_HOP,
    )

    out_dir      = os.path.dirname(os.path.abspath(__file__))
    outline_path = os.path.join(out_dir, OUTLINE_FILE)
    fill_path    = os.path.join(out_dir, FILL_FILE)

    with open(outline_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_outline())

    with open(fill_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_fill())

    base_z   = gen._base_z()
    wall_top = gen._wall_z(args.wall_layers - 1) if args.wall_layers else base_z
    print(f"Wrote: {outline_path}")
    print(f"  Base layer  Z={base_z:.2f} mm  (concentric fill, r={args.tower_radius:.1f} mm)")
    print(f"  Wall layers Z={base_z + args.layer_height:.2f}–{wall_top:.2f} mm  ({args.wall_layers} layers)")
    print(f"Wrote: {fill_path}")
    print(f"  Fill layer  Z={gen._wall_z(0):.2f} mm  (inside cup, r={args.tower_radius - args.inner_margin:.1f} mm)")


if __name__ == "__main__":
    main()
