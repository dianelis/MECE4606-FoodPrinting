#!/usr/bin/env python3
"""
generate_multi_ingredient_spirograph.py — Generate a multi-material spirograph cup.

SPIROGRAPH STRUCTURE
────────────────────
  Outline file  (di2256_spirograph_outline.gcode):
    Layer 1  → solid spirograph base built from scaled concentric copies
    Layers 2+ → outer spirograph wall only

  Fill file     (di2256_spirograph_fill.gcode):
    Layers 2+ → scaled interior spirograph rings inside the wall
    (use with a second syringe / second material)

This mirrors the fort workflow and print settings, but swaps the circular
geometry for a 6-loop epitrochoid spirograph shape.
"""

import argparse
import math
import os
import sys


# ─── Defaults ────────────────────────────────────────────────────────────────

WALL_LAYERS = 8
LAYER_HEIGHT = 1.0
FIRST_LAYER_Z = 5.5
FILL_Z_OFFSET = 2.0

CENTER_X = 100.0
CENTER_Y = 100.0

# Match the existing spirograph V4 silhouette: outer diameter ~= 52 mm.
BASE_R = 18.0
BASE_r = 3.0
BASE_d = 5.0

RING_STEP = 2.0
INNER_MARGIN = 3.0
POINTS_PER_REV = 360

PRINT_SPEED = 800
TRAVEL_SPEED = 1200
EXTRUSION_MULT = 0.025
FIRST_RING_REPS = 5
RETRACT_DIST = 1.5
Z_HOP = 1.0

OUTLINE_FILE = "di2256_spirograph_outline.gcode"
FILL_FILE = "di2256_spirograph_fill.gcode"


# ─── Geometry Helpers ────────────────────────────────────────────────────────

def compute_num_revolutions(R, r):
    """Number of full revolutions of t needed to close the curve."""
    g = math.gcd(int(R), int(r))
    return int(r) // g


def compute_num_loops(R, r):
    """Number of major loops / cusps in the pattern."""
    g = math.gcd(int(R), int(r))
    return int(R) // g


def epitrochoid_points(R, r, d, num_revs, total_points):
    """Return a closed epitrochoid centered at the origin."""
    pts = []
    s = R + r
    ratio = s / r
    for i in range(total_points + 1):
        t = 2.0 * math.pi * num_revs * i / total_points
        x = s * math.cos(t) - d * math.cos(ratio * t)
        y = s * math.sin(t) - d * math.sin(ratio * t)
        pts.append((x, y))
    return pts


def transform_points(points, cx, cy, scale=1.0, rotation_deg=0.0):
    """Scale and rotate a curve about the origin, then translate to (cx, cy)."""
    rot = math.radians(rotation_deg)
    cos_r = math.cos(rot)
    sin_r = math.sin(rot)
    out = []
    for x0, y0 in points:
        xs = x0 * scale
        ys = y0 * scale
        x = cx + xs * cos_r - ys * sin_r
        y = cy + xs * sin_r + ys * cos_r
        out.append((x, y))
    return out


def dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


# ─── G-code Generator ────────────────────────────────────────────────────────

class MultiIngredientSpirographGenerator:
    def __init__(
        self,
        *,
        wall_layers,
        layer_height,
        first_z,
        cx,
        cy,
        R,
        r,
        d,
        ring_step,
        inner_margin,
        points_per_rev,
        print_speed,
        travel_speed,
        extrusion_mult,
        retract,
        z_hop,
        first_ring_reps,
    ):
        self.wall_layers = wall_layers
        self.layer_height = layer_height
        self.first_z = first_z
        self.cx = cx
        self.cy = cy
        self.R = R
        self.r = r
        self.d = d
        self.ring_step = ring_step
        self.inner_margin = inner_margin
        self.points_per_rev = points_per_rev
        self.print_speed = print_speed
        self.travel_speed = travel_speed
        self.e_mult = extrusion_mult
        self.retract = retract
        self.z_hop = z_hop
        self.first_ring_reps = first_ring_reps

        self.num_revs = compute_num_revolutions(R, r)
        self.num_loops = compute_num_loops(R, r)
        self.total_points = self.points_per_rev * self.num_revs
        self.base_curve = epitrochoid_points(R, r, d, self.num_revs, self.total_points)
        self.outer_radius = max(math.hypot(x, y) for x, y in self.base_curve)

    # ── layer Z helpers ──

    def _base_z(self):
        return self.first_z

    def _wall_z(self, wall_idx):
        return self.first_z + (wall_idx + 1) * self.layer_height

    # ── low-level emitters ──

    def _header(self, mode, extra_notes=""):
        lines = []
        lines.append(f"; Diane Spirograph — {mode} G-code")
        lines.append("; Food Printing assignment")
        lines.append(";")
        lines.append("; MULTI-INGREDIENT SPIROGRAPH:")
        lines.append(";   Outline: solid base (layer 1) + outer spirograph wall (layers 2+)")
        lines.append(";   Fill   : scaled interior spirograph rings (second material)")
        lines.append(";")
        lines.append(f"; Wall layers: {self.wall_layers}")
        lines.append(f"; Layer height: {self.layer_height:.1f} mm")
        lines.append(f"; Base Z: {self._base_z():.2f} mm")
        wall_top = self._wall_z(self.wall_layers - 1) if self.wall_layers else self._base_z()
        lines.append(f"; Wall top Z: {wall_top:.2f} mm")
        lines.append(f"; Epitrochoid: R={self.R:.1f}, r={self.r:.1f}, d={self.d:.1f}")
        lines.append(f"; Loops: {self.num_loops}  |  Revolutions: {self.num_revs}")
        lines.append(f"; Outer radius: {self.outer_radius:.1f} mm")
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

    def _emit_path(self, lines, points, z, e_total, retracted, label, initial_safe_z=None):
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
            dxy = dist(points[i - 1], points[i])
            if dxy < 0.001:
                continue
            e_total += dxy * self.e_mult
            lines.append(
                f"G1 X{points[i][0]:.3f} Y{points[i][1]:.3f} "
                f"E{e_total:.4f} F{self.print_speed}"
            )

        e_total -= self.retract
        lines.append(f"G1 E{e_total:.4f} F{self.travel_speed}   ; Retract")
        return e_total, True

    def _build_scales(self, max_scale):
        """Use fort-style radial stepping, but map it onto scaled spirograph copies."""
        scales = []
        max_extent = self.outer_radius * max_scale
        radius = self.ring_step
        while radius <= max_extent:
            scales.append(radius / self.outer_radius)
            radius += self.ring_step
        if not scales or scales[-1] < max_scale:
            scales.append(max_scale)
        return scales

    def _emit_scaled_fill(self, lines, z, e_total, retracted, max_scale, label_prefix, safe_z=None):
        scales = self._build_scales(max_scale)
        for curve_idx, scale in enumerate(scales):
            reps = self.first_ring_reps if curve_idx == 0 else 1
            pts = transform_points(self.base_curve, self.cx, self.cy, scale=scale)
            if curve_idx % 2 == 1:
                pts = list(reversed(pts))
            for rep in range(reps):
                rep_label = f"{label_prefix} curve {curve_idx + 1} (scale={scale:.3f})"
                if reps > 1:
                    rep_label += f" rep {rep + 1}/{reps}"
                e_total, retracted = self._emit_path(
                    lines, pts, z, e_total, retracted, rep_label, initial_safe_z=safe_z
                )
                safe_z = None
        return e_total, retracted

    # ── public generators ──

    def generate_outline(self):
        """
        Layer 1 : solid spirograph base made from scaled copies.
        Layers 2+: outer spirograph wall only.
        """
        lines = self._header(
            "Outline",
            extra_notes="Layer 1=solid spirograph base  |  Layers 2+= outer spirograph wall",
        )
        e_total = 0.0
        retracted = False
        current_z = self._base_z()

        z = self._base_z()
        lines.append(f"; === LAYER 1 — SOLID SPIROGRAPH BASE  (Z={z:.2f} mm) ===")
        e_total, retracted = self._emit_scaled_fill(
            lines,
            z,
            e_total,
            retracted,
            max_scale=1.0,
            label_prefix="base",
            safe_z=z + 20.0,
        )

        wall_pts = transform_points(self.base_curve, self.cx, self.cy, scale=1.0)
        for w in range(self.wall_layers):
            z = self._wall_z(w)
            current_z = z
            lines.append("")
            lines.append(f"; === LAYER {w + 2} — WALL  (Z={z:.2f} mm) ===")
            e_total, retracted = self._emit_path(
                lines, wall_pts, z, e_total, retracted, "outer spirograph wall"
            )

        self._finish(lines, current_z)
        return "\n".join(lines) + "\n"

    def generate_fill(self):
        """
        Print multiple interior spirograph layers with a second material.
        """
        max_scale = (self.outer_radius - self.inner_margin) / self.outer_radius
        wall_top_z = self._wall_z(self.wall_layers - 1) if self.wall_layers else self._base_z()
        safe_z_over_wall = wall_top_z + 10.0 + FILL_Z_OFFSET

        lines = self._header(
            "Fill (second material)",
            extra_notes=(
                f"Fill layers inside the spirograph build to Z={wall_top_z + FILL_Z_OFFSET:.2f} mm "
                f"(shifted up {FILL_Z_OFFSET} mm)"
            ),
        )
        e_total = 0.0
        retracted = False
        current_z = safe_z_over_wall

        for w in range(self.wall_layers):
            fill_z = self._wall_z(w) + FILL_Z_OFFSET
            current_z = fill_z
            lines.append("")
            lines.append(
                f"; === FILL LAYER {w + 1}/{self.wall_layers} — INSIDE SPIROGRAPH  "
                f"(Z={fill_z:.2f} mm) ==="
            )
            layer_safe_z = safe_z_over_wall if w == 0 else None
            e_total, retracted = self._emit_scaled_fill(
                lines,
                fill_z,
                e_total,
                retracted,
                max_scale=max_scale,
                label_prefix=f"fill L{w + 1}",
                safe_z=layer_safe_z,
            )

        self._finish(lines, current_z)
        return "\n".join(lines) + "\n"


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-material spirograph G-code (solid base + wall + fill).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                               Default multi-ingredient spirograph
  %(prog)s --wall-layers 4               Shorter spirograph wall
  %(prog)s --first-z 3.0 --ring-step 3.5 Wider spacing between interior curves
  %(prog)s --R 20 --r 4 --d 6            5-loop variant
""",
    )
    parser.add_argument("--wall-layers", type=int, default=WALL_LAYERS,
                        help=f"Number of wall layers above the base (default: {WALL_LAYERS})")
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT,
                        help=f"Layer height in mm (default: {LAYER_HEIGHT})")
    parser.add_argument("--first-z", type=float, default=FIRST_LAYER_Z,
                        help=f"Z height of the base layer in mm (default: {FIRST_LAYER_Z})")
    parser.add_argument("--R", type=float, default=BASE_R,
                        help=f"Fixed circle radius for the epitrochoid (default: {BASE_R})")
    parser.add_argument("--r", type=float, default=BASE_r,
                        help=f"Rolling circle radius (default: {BASE_r})")
    parser.add_argument("--d", type=float, default=BASE_d,
                        help=f"Pen offset (default: {BASE_d})")
    parser.add_argument("--ring-step", type=float, default=RING_STEP,
                        help=f"Spacing between scaled interior paths in mm (default: {RING_STEP})")
    parser.add_argument("--inner-margin", type=float, default=INNER_MARGIN,
                        help=f"Margin between the outer wall and fill paths in mm (default: {INNER_MARGIN})")
    parser.add_argument("--resolution", type=int, default=POINTS_PER_REV,
                        help=f"Points per revolution for the curve (default: {POINTS_PER_REV})")
    args = parser.parse_args()

    if args.wall_layers < 0:
        print("error: --wall-layers must be >= 0", file=sys.stderr)
        sys.exit(2)
    if args.R <= 0 or args.r <= 0:
        print("error: --R and --r must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.d < 0:
        print("error: --d must be >= 0", file=sys.stderr)
        sys.exit(2)
    if args.ring_step <= 0:
        print("error: --ring-step must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.inner_margin < 0:
        print("error: --inner-margin must be >= 0", file=sys.stderr)
        sys.exit(2)
    if args.resolution <= 0:
        print("error: --resolution must be > 0", file=sys.stderr)
        sys.exit(2)

    gen = MultiIngredientSpirographGenerator(
        wall_layers=args.wall_layers,
        layer_height=args.layer_height,
        first_z=args.first_z,
        cx=CENTER_X,
        cy=CENTER_Y,
        R=args.R,
        r=args.r,
        d=args.d,
        ring_step=args.ring_step,
        inner_margin=args.inner_margin,
        points_per_rev=args.resolution,
        print_speed=PRINT_SPEED,
        travel_speed=TRAVEL_SPEED,
        extrusion_mult=EXTRUSION_MULT,
        retract=RETRACT_DIST,
        z_hop=Z_HOP,
        first_ring_reps=FIRST_RING_REPS,
    )

    if gen.outer_radius <= args.inner_margin:
        print("error: --inner-margin must be smaller than the spirograph outer radius", file=sys.stderr)
        sys.exit(2)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    outline_path = os.path.join(out_dir, OUTLINE_FILE)
    fill_path = os.path.join(out_dir, FILL_FILE)

    with open(outline_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_outline())

    with open(fill_path, "w", encoding="utf-8") as fh:
        fh.write(gen.generate_fill())

    base_z = gen._base_z()
    wall_top = gen._wall_z(args.wall_layers - 1) if args.wall_layers else base_z
    fill_scale = (gen.outer_radius - args.inner_margin) / gen.outer_radius

    print(f"Wrote: {outline_path}")
    print(f"  Base layer  Z={base_z:.2f} mm  (solid scaled spirograph fill)")
    print(f"  Wall layers Z={base_z + args.layer_height:.2f}–{wall_top:.2f} mm  ({args.wall_layers} layers)")
    print(f"Wrote: {fill_path}")
    print(
        f"  Fill layers Z={gen._wall_z(0) + FILL_Z_OFFSET:.2f}–{wall_top + FILL_Z_OFFSET:.2f} mm  "
        f"({args.wall_layers} layers, max scale={fill_scale:.3f})"
    )


if __name__ == "__main__":
    main()
