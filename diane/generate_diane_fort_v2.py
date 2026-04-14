#!/usr/bin/env python3
"""
generate_diane_fort_v2.py — Generate a tall fort with a stacked circular tower.

This script writes two separate G-code files:
  1. A fort outline base with a circular tower stacked above it
  2. A matching interior fill for both the fort base and tower

Usage:
    python generate_diane_fort_v2.py
    python generate_diane_fort_v2.py --tower-layers 24 --tower-radius 14
    python generate_diane_fort_v2.py --base-layers 4 --radius 30
"""

import argparse
import math
import os
import sys


# ─── Defaults ────────────────────────────────────────────────────────────────

BASE_LAYERS       = 3
TOWER_LAYERS      = 20
LAYER_HEIGHT      = 2.0
FIRST_LAYER_Z     = 2.0

CENTER_X          = 100.0
CENTER_Y          = 100.0

FORT_RADIUS       = 28.0
NOTCH_DEPTH       = 3.0
BATTLEMENTS       = 18

TOWER_RADIUS      = 12.0
RING_STEP         = 4.0
INNER_MARGIN      = 3.0
POINTS_PER_RING   = 72

PRINT_SPEED       = 300
TRAVEL_SPEED      = 1200
EXTRUSION_MULT    = 0.065
RETRACT_DIST      = 1.5
Z_HOP             = 1.0

OUTLINE_FILE      = "di2256_diane_fort_outline_v2.gcode"
FILL_FILE         = "di2256_diane_fort_fill_v2.gcode"


# ─── Geometry Helpers ────────────────────────────────────────────────────────

def rotate_point(x, y, cx, cy, angle_deg):
    """Rotate point (x, y) about (cx, cy) by angle_deg degrees."""
    a = math.radians(angle_deg)
    dx = x - cx
    dy = y - cy
    xr = dx * math.cos(a) - dy * math.sin(a)
    yr = dx * math.sin(a) + dy * math.cos(a)
    return (cx + xr, cy + yr)


def battlement_ring(cx, cy, radius, notch_depth, battlements, rotation_deg=0.0):
    """Return a closed fort-like ring by alternating between outer/inner radius."""
    pts = []
    total_steps = battlements * 2
    inner_radius = radius - notch_depth

    for i in range(total_steps + 1):
        theta = 2.0 * math.pi * i / total_steps
        r = radius if i % 2 == 0 else inner_radius
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        pts.append(rotate_point(x, y, cx, cy, rotation_deg))

    return pts


def circle_ring(cx, cy, radius, points_per_ring, rotation_deg=0.0):
    """Return a closed circular ring."""
    pts = []
    for i in range(points_per_ring + 1):
        theta = 2.0 * math.pi * i / points_per_ring
        x = cx + radius * math.cos(theta)
        y = cy + radius * math.sin(theta)
        pts.append(rotate_point(x, y, cx, cy, rotation_deg))
    return pts


def ring_distance(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


# ─── G-code Generator ────────────────────────────────────────────────────────

class FortTowerGenerator:
    def __init__(
        self,
        *,
        base_layers,
        tower_layers,
        layer_height,
        first_z,
        cx,
        cy,
        fort_radius,
        notch_depth,
        battlements,
        tower_radius,
        ring_step,
        inner_margin,
        points_per_ring,
        print_speed,
        travel_speed,
        extrusion_mult,
        retract,
        z_hop,
    ):
        self.base_layers = base_layers
        self.tower_layers = tower_layers
        self.layer_height = layer_height
        self.first_z = first_z
        self.cx = cx
        self.cy = cy
        self.fort_radius = fort_radius
        self.notch_depth = notch_depth
        self.battlements = battlements
        self.tower_radius = tower_radius
        self.ring_step = ring_step
        self.inner_margin = inner_margin
        self.points_per_ring = points_per_ring
        self.print_speed = print_speed
        self.travel_speed = travel_speed
        self.e_mult = extrusion_mult
        self.retract = retract
        self.z_hop = z_hop

    @property
    def total_layers(self):
        return self.base_layers + self.tower_layers

    def _header(self, mode):
        lines = []
        lines.append(f"; Diane Fort V2 — {mode} G-code")
        lines.append("; Food Printing assignment")
        lines.append(";")
        lines.append(f"; Base fort layers: {self.base_layers}")
        lines.append(f"; Circular tower layers: {self.tower_layers}")
        lines.append(f"; Total layers: {self.total_layers}")
        lines.append(f"; Layer height: {self.layer_height:.1f}mm")
        lines.append(f"; First layer Z: {self.first_z:.1f}mm")
        lines.append(f"; Center: ({self.cx:.0f}, {self.cy:.0f})")
        lines.append(f"; Fort radius: {self.fort_radius:.1f}mm")
        lines.append(f"; Tower radius: {self.tower_radius:.1f}mm")
        lines.append(f"; Battlements: {self.battlements}")
        lines.append(f"; Notch depth: {self.notch_depth:.1f}mm")
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
        lines.append(f"G1 X0 Y0 F{self.travel_speed}   ; Move to home")
        lines.append("M84              ; Disable motors")
        lines.append("")
        lines.append("; === END ===")

    def _emit_closed_path(self, lines, points, z, e_total, retracted, label):
        x0, y0 = points[0]
        lines.append(f"G1 Z{z + self.z_hop:.2f} F600   ; Z-hop")
        lines.append(f"G1 X{x0:.3f} Y{y0:.3f} F{self.travel_speed}   ; Travel to {label}")
        lines.append(f"G1 Z{z:.2f} F300   ; Lower to layer height")

        if retracted:
            e_total += self.retract
            lines.append(f"G1 E{e_total:.4f} F{self.travel_speed}   ; Prime")
            retracted = False

        for i in range(1, len(points)):
            p_start = points[i - 1]
            p_end = points[i]
            d = ring_distance(p_start, p_end)
            if d < 0.001:
                continue
            e_total += d * self.e_mult
            lines.append(
                f"G1 X{p_end[0]:.3f} Y{p_end[1]:.3f} "
                f"E{e_total:.4f} F{self.print_speed}"
            )

        e_total -= self.retract
        lines.append(f"G1 E{e_total:.4f} F{self.travel_speed}   ; Retract")
        return e_total, True

    def _layer_z(self, layer_idx):
        return self.first_z + layer_idx * self.layer_height

    def _base_fill_max_radius(self):
        return self.fort_radius - self.notch_depth - self.inner_margin

    def _tower_fill_max_radius(self):
        return self.tower_radius - self.inner_margin

    def generate_outline(self):
        lines = self._header("Outline")
        e_total = 0.0
        retracted = False
        current_z = self.first_z

        for layer_idx in range(self.base_layers):
            z = self._layer_z(layer_idx)
            current_z = z
            rotation = layer_idx * (180.0 / self.battlements)
            points = battlement_ring(
                self.cx,
                self.cy,
                self.fort_radius,
                self.notch_depth,
                self.battlements,
                rotation_deg=rotation,
            )

            lines.append("")
            lines.append(
                f"; === BASE LAYER {layer_idx + 1}/{self.base_layers} "
                f"(Z={z:.1f}mm, fort rotation={rotation:.1f}°) ==="
            )
            e_total, retracted = self._emit_closed_path(
                lines,
                points,
                z,
                e_total,
                retracted,
                "fort outline",
            )

        for tower_idx in range(self.tower_layers):
            layer_idx = self.base_layers + tower_idx
            z = self._layer_z(layer_idx)
            current_z = z
            points = circle_ring(
                self.cx,
                self.cy,
                self.tower_radius,
                self.points_per_ring,
            )

            lines.append("")
            lines.append(
                f"; === TOWER LAYER {tower_idx + 1}/{self.tower_layers} "
                f"(Z={z:.1f}mm, circular tower) ==="
            )
            e_total, retracted = self._emit_closed_path(
                lines,
                points,
                z,
                e_total,
                retracted,
                "tower outline",
            )

        self._finish(lines, current_z)
        return "\n".join(lines) + "\n"

    def generate_fill(self):
        lines = self._header("Fill")
        e_total = 0.0
        retracted = False
        current_z = self.first_z

        base_max_radius = self._base_fill_max_radius()
        tower_max_radius = self._tower_fill_max_radius()

        for layer_idx in range(self.base_layers):
            z = self._layer_z(layer_idx)
            current_z = z
            rotation = layer_idx * (180.0 / self.points_per_ring)

            lines.append("")
            lines.append(
                f"; === BASE LAYER {layer_idx + 1}/{self.base_layers} "
                f"(Z={z:.1f}mm, fort fill) ==="
            )

            ring_index = 0
            radius = base_max_radius
            while radius >= self.ring_step:
                points = circle_ring(
                    self.cx,
                    self.cy,
                    radius,
                    self.points_per_ring,
                    rotation_deg=rotation,
                )
                if ring_index % 2 == 1:
                    points = list(reversed(points))

                e_total, retracted = self._emit_closed_path(
                    lines,
                    points,
                    z,
                    e_total,
                    retracted,
                    f"fort fill ring {ring_index + 1}",
                )
                ring_index += 1
                radius -= self.ring_step

        for tower_idx in range(self.tower_layers):
            layer_idx = self.base_layers + tower_idx
            z = self._layer_z(layer_idx)
            current_z = z

            lines.append("")
            lines.append(
                f"; === TOWER LAYER {tower_idx + 1}/{self.tower_layers} "
                f"(Z={z:.1f}mm, tower fill) ==="
            )

            ring_index = 0
            radius = tower_max_radius
            while radius >= self.ring_step:
                points = circle_ring(
                    self.cx,
                    self.cy,
                    radius,
                    self.points_per_ring,
                )
                if ring_index % 2 == 1:
                    points = list(reversed(points))

                e_total, retracted = self._emit_closed_path(
                    lines,
                    points,
                    z,
                    e_total,
                    retracted,
                    f"tower fill ring {ring_index + 1}",
                )
                ring_index += 1
                radius -= self.ring_step

        self._finish(lines, current_z)
        return "\n".join(lines) + "\n"


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a tall fort with a stacked circular tower.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s
  %(prog)s --tower-layers 24 --tower-radius 14
  %(prog)s --base-layers 4 --radius 30
""",
    )
    parser.add_argument("--base-layers", type=int, default=BASE_LAYERS,
                        help=f"Number of fort base layers (default: {BASE_LAYERS})")
    parser.add_argument("--tower-layers", type=int, default=TOWER_LAYERS,
                        help=f"Number of stacked circular tower layers (default: {TOWER_LAYERS})")
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT,
                        help=f"Layer height in mm (default: {LAYER_HEIGHT})")
    parser.add_argument("--first-z", type=float, default=FIRST_LAYER_Z,
                        help=f"First layer Z in mm (default: {FIRST_LAYER_Z})")
    parser.add_argument("--radius", type=float, default=FORT_RADIUS,
                        help=f"Outer fort radius in mm (default: {FORT_RADIUS})")
    parser.add_argument("--notch-depth", type=float, default=NOTCH_DEPTH,
                        help=f"Battlement notch depth in mm (default: {NOTCH_DEPTH})")
    parser.add_argument("--battlements", type=int, default=BATTLEMENTS,
                        help=f"Number of battlements (default: {BATTLEMENTS})")
    parser.add_argument("--tower-radius", type=float, default=TOWER_RADIUS,
                        help=f"Circular tower radius in mm (default: {TOWER_RADIUS})")
    parser.add_argument("--ring-step", type=float, default=RING_STEP,
                        help=f"Spacing between fill rings in mm (default: {RING_STEP})")
    parser.add_argument("--inner-margin", type=float, default=INNER_MARGIN,
                        help=f"Gap between wall and fill in mm (default: {INNER_MARGIN})")
    args = parser.parse_args()

    if args.base_layers < 1:
        print("error: --base-layers must be >= 1", file=sys.stderr)
        sys.exit(2)
    if args.tower_layers < 1:
        print("error: --tower-layers must be >= 1", file=sys.stderr)
        sys.exit(2)
    if args.radius <= 0:
        print("error: --radius must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.notch_depth <= 0 or args.notch_depth >= args.radius:
        print("error: --notch-depth must be > 0 and less than --radius", file=sys.stderr)
        sys.exit(2)
    if args.battlements < 6:
        print("error: --battlements must be >= 6", file=sys.stderr)
        sys.exit(2)
    if args.tower_radius <= 0:
        print("error: --tower-radius must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.tower_radius >= (args.radius - args.notch_depth):
        print("error: --tower-radius must fit inside the fort wall", file=sys.stderr)
        sys.exit(2)
    if args.ring_step <= 0:
        print("error: --ring-step must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.inner_margin < 0:
        print("error: --inner-margin must be >= 0", file=sys.stderr)
        sys.exit(2)
    if args.tower_radius <= args.inner_margin:
        print("error: --tower-radius must be greater than --inner-margin", file=sys.stderr)
        sys.exit(2)

    generator = FortTowerGenerator(
        base_layers=args.base_layers,
        tower_layers=args.tower_layers,
        layer_height=args.layer_height,
        first_z=args.first_z,
        cx=CENTER_X,
        cy=CENTER_Y,
        fort_radius=args.radius,
        notch_depth=args.notch_depth,
        battlements=args.battlements,
        tower_radius=args.tower_radius,
        ring_step=args.ring_step,
        inner_margin=args.inner_margin,
        points_per_ring=POINTS_PER_RING,
        print_speed=PRINT_SPEED,
        travel_speed=TRAVEL_SPEED,
        extrusion_mult=EXTRUSION_MULT,
        retract=RETRACT_DIST,
        z_hop=Z_HOP,
    )

    out_dir = os.path.dirname(os.path.abspath(__file__))
    outline_path = os.path.join(out_dir, OUTLINE_FILE)
    fill_path = os.path.join(out_dir, FILL_FILE)

    with open(outline_path, "w", encoding="utf-8") as fh:
        fh.write(generator.generate_outline())

    with open(fill_path, "w", encoding="utf-8") as fh:
        fh.write(generator.generate_fill())

    print(f"Wrote {outline_path}")
    print(f"Wrote {fill_path}")


if __name__ == "__main__":
    main()
