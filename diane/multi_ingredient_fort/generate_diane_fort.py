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
FILL_Z_OFFSET     = 2.0        # shift the jam filling up by 2mm
TOPPER_LAYERS     = 3          # spirograph layers stacked on top of the fill

CENTER_X          = 100.0
CENTER_Y          = 100.0

# Match spirograph v4 outer diameter of 52 mm.
TOWER_RADIUS      = 26.0
RING_STEP         = 2.0        # spacing between concentric fill rings (mm) — tight, no gaps
INNER_MARGIN      = 3.0        # gap between outer wall and innermost fill ring (mm)
POINTS_PER_RING   = 72         # polygon resolution per circle
SPIROGRAPH_R      = 18.0       # fixed circle radius
SPIROGRAPH_r      = 3.0        # rolling circle radius
SPIROGRAPH_d      = 5.0        # pen offset
SPIROGRAPH_POINTS_PER_REV = 360
TOPPER_SCALE      = 0.35       # print the topper smaller than the original spirograph size

PRINT_SPEED       = 800        # mm/min — faster = thinner deposit, less blobbing
TRAVEL_SPEED      = 1200
EXTRUSION_MULT    = 0.025      # E mm per mm of XY travel (tuned thin)
FIRST_RING_REPS   = 5          # repeat the innermost ring this many times to prime/push down
RETRACT_DIST      = 1.5
Z_HOP             = 1.0

OUTLINE_FILE      = "di2256_fort_outline.gcode"
FILL_FILE         = "di2256_fort_fill.gcode"
TOPPER_FILE       = "di2256_fort_spirograph_topper.gcode"


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


def compute_num_revolutions(R, r):
    """Number of full revolutions of t needed to close the epitrochoid."""
    g = math.gcd(int(R), int(r))
    return int(r) // g


def epitrochoid_points(R, r, d, num_revs, total_points, cx, cy):
    """Return a closed epitrochoid translated to (cx, cy)."""
    pts = []
    s = R + r
    ratio = s / r
    for i in range(total_points + 1):
        t = 2.0 * math.pi * num_revs * i / total_points
        x = cx + s * math.cos(t) - d * math.cos(ratio * t)
        y = cy + s * math.sin(t) - d * math.sin(ratio * t)
        pts.append((x, y))
    return pts


def scale_points(points, cx, cy, scale):
    """Scale a path about the print center."""
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in points]


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
        topper_layers,
        spirograph_R,
        spirograph_r,
        spirograph_d,
        spirograph_points_per_rev,
        topper_scale,
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
        self.topper_layers    = topper_layers
        self.spirograph_R     = spirograph_R
        self.spirograph_r     = spirograph_r
        self.spirograph_d     = spirograph_d
        self.spirograph_points_per_rev = spirograph_points_per_rev
        self.topper_scale     = topper_scale
        self.spirograph_num_revs = compute_num_revolutions(spirograph_R, spirograph_r)
        self.spirograph_total_points = self.spirograph_num_revs * spirograph_points_per_rev

    # ── layer Z helpers ──

    def _base_z(self):
        return self.first_z

    def _wall_z(self, wall_idx):
        """wall_idx 0 = first wall layer directly above the base."""
        return self.first_z + (wall_idx + 1) * self.layer_height

    def _fill_top_z(self):
        if self.wall_layers:
            return self._wall_z(self.wall_layers - 1) + FILL_Z_OFFSET
        return self._base_z() + FILL_Z_OFFSET

    def _topper_z(self, topper_idx):
        """topper_idx 0 = first spirograph layer above the fill."""
        return self._fill_top_z() + (topper_idx + 1) * self.layer_height

    # ── low-level emitters ──

    def _header(self, mode, extra_notes="", home_axes=True):
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
        if home_axes:
            lines.append("G28              ; Home all axes")
        else:
            lines.append("; Continuation file: keep printer coordinates from the completed fort print")
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

    def _emit_path(self, lines, points, z, e_total, retracted, label, initial_safe_z=None):
        """Travel to start of path, lower, prime if needed, extrude, retract."""
        x0, y0 = points[0]
        if initial_safe_z is not None:
            lines.append(f"G1 Z{initial_safe_z:.2f} F600   ; Initial safe Z-hop over wall")
            lines.append(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Safe travel → {label}")
        else:
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

    def _emit_concentric_fill(self, lines, z, e_total, retracted, max_radius, label_prefix, safe_z=None):
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
                    lines, pts, z, e_total, retracted, rep_label, initial_safe_z=safe_z
                )
                safe_z = None  # Only use safe_z for the very first approach
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
            label_prefix="base",
            safe_z=z + 20.0
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
        Multiple layers of concentric rings inside the cup walls, 
        building up piece by piece to the same height as the fort.
        Print this with a second material (e.g. jam) after the outline.
        """
        max_r  = self.tower_radius - self.inner_margin
        wall_top_z = self._wall_z(self.wall_layers - 1)
        # We add 2.0mm to the fill Z as requested
        safe_z_over_wall = wall_top_z + 10.0 + FILL_Z_OFFSET  

        lines = self._header(
            "Fill (second material)",
            extra_notes=f"Fill layers inside cup building to Z={wall_top_z + FILL_Z_OFFSET:.2f} mm (shifted up {FILL_Z_OFFSET}mm)"
        )
        e_total  = 0.0
        retracted = False

        current_z = safe_z_over_wall

        for w in range(self.wall_layers):
            fill_z = self._wall_z(w) + FILL_Z_OFFSET
            current_z = fill_z

            lines.append("")
            lines.append(f"; === FILL LAYER {w+1}/{self.wall_layers} — INSIDE CUP  (Z={fill_z:.2f} mm) ===")
            
            # The very first move from home must jump over the built wall
            layer_safe_z = safe_z_over_wall if w == 0 else None

            e_total, retracted = self._emit_concentric_fill(
                lines, fill_z, e_total, retracted,
                max_radius=max_r,
                label_prefix=f"fill L{w+1}",
                safe_z=layer_safe_z
            )

        self._finish(lines, current_z)
        return "\n".join(lines) + "\n"

    def generate_spirograph_topper(self):
        """
        Print a 3-layer spirograph on top of the completed fort fill.
        This file continues from the fort's final fill height instead of
        starting back at the original base layer.
        """
        lines = self._header(
            "Spirograph Topper",
            extra_notes=(
                f"Continuation after fort fill: first topper layer starts at Z={self._topper_z(0):.2f} mm "
                f"(fill ended at Z={self._fill_top_z():.2f} mm, topper scale={self.topper_scale:.2f}x)"
            ),
            home_axes=False,
        )
        e_total = 0.0
        retracted = False
        current_z = self._topper_z(0)
        safe_z = self._fill_top_z() + 10.0
        pts = scale_points(
            epitrochoid_points(
                self.spirograph_R,
                self.spirograph_r,
                self.spirograph_d,
                self.spirograph_num_revs,
                self.spirograph_total_points,
                self.cx,
                self.cy,
            ),
            self.cx,
            self.cy,
            self.topper_scale,
        )

        for t in range(self.topper_layers):
            z = self._topper_z(t)
            current_z = z
            lines.append("")
            lines.append(
                f"; === TOPPER LAYER {t + 1}/{self.topper_layers} — SPIROGRAPH  (Z={z:.2f} mm) ==="
            )
            layer_safe_z = safe_z if t == 0 else None
            e_total, retracted = self._emit_path(
                lines,
                pts,
                z,
                e_total,
                retracted,
                "spirograph topper",
                initial_safe_z=layer_safe_z,
            )

        self._finish(lines, current_z)
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
        topper_layers=TOPPER_LAYERS,
        spirograph_R=SPIROGRAPH_R,
        spirograph_r=SPIROGRAPH_r,
        spirograph_d=SPIROGRAPH_d,
        spirograph_points_per_rev=SPIROGRAPH_POINTS_PER_REV,
        topper_scale=TOPPER_SCALE,
    )

    out_dir      = os.path.dirname(os.path.abspath(__file__))
    outline_path = os.path.join(out_dir, OUTLINE_FILE)
    fill_path    = os.path.join(out_dir, FILL_FILE)
    topper_path  = os.path.join(out_dir, TOPPER_FILE)

    with open(outline_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_outline())

    with open(fill_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_fill())

    with open(topper_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_spirograph_topper())

    base_z   = gen._base_z()
    wall_top = gen._wall_z(args.wall_layers - 1) if args.wall_layers else base_z
    fill_top = gen._fill_top_z()
    print(f"Wrote: {outline_path}")
    print(f"  Base layer  Z={base_z:.2f} mm  (concentric fill, r={args.tower_radius:.1f} mm)")
    print(f"  Wall layers Z={base_z + args.layer_height:.2f}–{wall_top:.2f} mm  ({args.wall_layers} layers)")
    print(f"Wrote: {fill_path}")
    print(f"  Fill layers Z={gen._wall_z(0) + FILL_Z_OFFSET:.2f}–{wall_top + FILL_Z_OFFSET:.2f} mm  ({args.wall_layers} layers, r={args.tower_radius - args.inner_margin:.1f} mm)")
    print(f"Wrote: {topper_path}")
    print(
        f"  Topper layers Z={gen._topper_z(0):.2f}–{gen._topper_z(gen.topper_layers - 1):.2f} mm  "
        f"({gen.topper_layers} layers, continuing above fill top at Z={fill_top:.2f} mm)"
    )


if __name__ == "__main__":
    main()
