#!/usr/bin/env python3
"""
gcode_to_svg.py — Convert G-code files to SVG visualizations.

Parses G-code movement commands (G0, G1, G2, G3) and renders the toolpath
as an SVG file. Supports absolute/relative positioning, extrusion-only
rendering, multi-layer color coding, and travel-move visualization.

Usage:
    python gcode_to_svg.py <input.gcode> [options]

Examples:
    python gcode_to_svg.py square.gcode
    python gcode_to_svg.py square.gcode -o output.svg
    python gcode_to_svg.py square.gcode --show-travel --scale 3
    python gcode_to_svg.py square.gcode --all-moves
"""

import argparse
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# ─── Configuration ───────────────────────────────────────────────────────────

LAYER_COLORS = [
    "#2563EB",  # blue
    "#DC2626",  # red
    "#16A34A",  # green
    "#D97706",  # amber
    "#9333EA",  # purple
    "#0891B2",  # cyan
    "#E11D48",  # rose
    "#4F46E5",  # indigo
]

TRAVEL_COLOR = "#94A3B8"
TRAVEL_DASH  = "4,3"
SVG_MARGIN   = 15
STROKE_WIDTH = 1.5


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class Point:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0


@dataclass
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float
    extruding: bool = False
    layer: int = 0
    is_arc: bool = False
    clockwise: bool = False
    cx: float = 0.0
    cy: float = 0.0
    r: float = 0.0


# ─── G-code Parser ──────────────────────────────────────────────────────────

class GCodeParser:
    def __init__(self, *, all_moves: bool = False, layer_height_threshold: float = 0.3):
        self.all_moves = all_moves
        self.layer_threshold = layer_height_threshold
        self.pos = Point()
        self.absolute_xy = True
        self.absolute_e = True
        self.segments: list[Segment] = []
        self.layer = 0
        self.last_extrusion_z = 0.0
        self._has_extruded = False

    def parse_file(self, filepath: str) -> list[Segment]:
        with open(filepath, "r") as f:
            for line in f:
                self._parse_line(line)
        return self.segments

    @staticmethod
    def _extract_params(line: str) -> dict[str, float]:
        params: dict[str, float] = {}
        for match in re.finditer(r"([A-Za-z])([+-]?\d*\.?\d+)", line):
            params[match.group(1).upper()] = float(match.group(2))
        return params

    def _parse_line(self, raw: str):
        line = raw.split(";")[0].strip()
        if not line:
            return
        params = self._extract_params(line)
        cmd = line.split()[0].upper() if line.split() else ""

        if cmd in ("G0", "G1"):
            self._handle_linear(params, rapid=(cmd == "G0"))
        elif cmd in ("G2", "G3"):
            self._handle_arc(params, clockwise=(cmd == "G2"))
        elif cmd == "G90":
            self.absolute_xy = True
        elif cmd == "G91":
            self.absolute_xy = False
        elif cmd == "G92":
            if "X" in params: self.pos.x = params["X"]
            if "Y" in params: self.pos.y = params["Y"]
            if "Z" in params: self.pos.z = params["Z"]
            if "E" in params: self.pos.e = params["E"]
        elif cmd == "M82":
            self.absolute_e = True
        elif cmd == "M83":
            self.absolute_e = False
        elif cmd == "G28":
            self.pos = Point()

    def _handle_linear(self, params: dict[str, float], rapid: bool):
        old = Point(self.pos.x, self.pos.y, self.pos.z, self.pos.e)

        if self.absolute_xy:
            self.pos.x = params.get("X", self.pos.x)
            self.pos.y = params.get("Y", self.pos.y)
            self.pos.z = params.get("Z", self.pos.z)
        else:
            self.pos.x += params.get("X", 0)
            self.pos.y += params.get("Y", 0)
            self.pos.z += params.get("Z", 0)

        old_e = self.pos.e
        if "E" in params:
            if self.absolute_e:
                self.pos.e = params["E"]
            else:
                self.pos.e += params["E"]

        extruding = self.pos.e > old_e

        # Layer detection: only triggers on extrusion at a new Z height.
        # Z-hops during travel moves are ignored.
        if extruding:
            if not self._has_extruded:
                self._has_extruded = True
                self.last_extrusion_z = self.pos.z
            elif self.pos.z - self.last_extrusion_z > self.layer_threshold:
                self.layer += 1
                self.last_extrusion_z = self.pos.z

        if old.x != self.pos.x or old.y != self.pos.y:
            if extruding or self.all_moves:
                self.segments.append(Segment(
                    x1=old.x, y1=old.y,
                    x2=self.pos.x, y2=self.pos.y,
                    extruding=extruding,
                    layer=self.layer,
                ))

    def _handle_arc(self, params: dict[str, float], clockwise: bool):
        old = Point(self.pos.x, self.pos.y, self.pos.z, self.pos.e)
        if self.absolute_xy:
            self.pos.x = params.get("X", self.pos.x)
            self.pos.y = params.get("Y", self.pos.y)
        else:
            self.pos.x += params.get("X", 0)
            self.pos.y += params.get("Y", 0)

        old_e = self.pos.e
        if "E" in params:
            if self.absolute_e:
                self.pos.e = params["E"]
            else:
                self.pos.e += params["E"]

        extruding = self.pos.e > old_e
        i = params.get("I", 0)
        j = params.get("J", 0)
        cx = old.x + i
        cy = old.y + j
        r = math.hypot(i, j)

        if extruding or self.all_moves:
            self.segments.append(Segment(
                x1=old.x, y1=old.y,
                x2=self.pos.x, y2=self.pos.y,
                extruding=extruding,
                layer=self.layer,
                is_arc=True, clockwise=clockwise,
                cx=cx, cy=cy, r=r,
            ))


# ─── SVG Renderer ────────────────────────────────────────────────────────────

class SVGRenderer:
    def __init__(self, segments, *, scale=2.0, stroke_width=STROKE_WIDTH,
                 show_travel=False, show_points=False, background="#FFFFFF"):
        self.segments = segments
        self.scale = scale
        self.stroke_width = stroke_width
        self.show_travel = show_travel
        self.show_points = show_points
        self.background = background

    def render(self) -> str:
        if not self.segments:
            return self._empty_svg()

        all_x = [s.x1 for s in self.segments] + [s.x2 for s in self.segments]
        all_y = [s.y1 for s in self.segments] + [s.y2 for s in self.segments]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        w = (max_x - min_x) * self.scale + 2 * SVG_MARGIN
        h = (max_y - min_y) * self.scale + 2 * SVG_MARGIN

        def tx(x): return (x - min_x) * self.scale + SVG_MARGIN
        def ty(y): return (max_y - y) * self.scale + SVG_MARGIN

        lines = []
        lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                      f'width="{w:.1f}" height="{h:.1f}" '
                      f'viewBox="0 0 {w:.1f} {h:.1f}">')
        lines.append(f'  <rect width="100%" height="100%" fill="{self.background}"/>')
        lines.append(f'  <title>G-code Toolpath</title>')

        # Travel moves
        if self.show_travel:
            travel = [s for s in self.segments if not s.extruding]
            if travel:
                lines.append(f'  <g id="travel" stroke="{TRAVEL_COLOR}" '
                             f'stroke-width="{self.stroke_width * 0.6:.2f}" '
                             f'stroke-dasharray="{TRAVEL_DASH}" fill="none" opacity="0.5">')
                for s in travel:
                    lines.append(self._seg(s, tx, ty))
                lines.append('  </g>')

        # Extrusion by layer
        max_layer = max(s.layer for s in self.segments)
        for li in range(max_layer + 1):
            segs = [s for s in self.segments if s.extruding and s.layer == li]
            if not segs:
                continue
            color = LAYER_COLORS[li % len(LAYER_COLORS)]
            lines.append(f'  <g id="layer-{li}" stroke="{color}" '
                         f'stroke-width="{self.stroke_width:.2f}" fill="none" '
                         f'stroke-linecap="round" stroke-linejoin="round">')
            for s in segs:
                lines.append(self._seg(s, tx, ty))
            lines.append('  </g>')

        # Start / end points
        if self.show_points:
            ext = [s for s in self.segments if s.extruding]
            if ext:
                r = self.stroke_width * 2
                lines.append(f'  <circle cx="{tx(ext[0].x1):.2f}" cy="{ty(ext[0].y1):.2f}" '
                             f'r="{r}" fill="#16A34A" opacity="0.8"/>  <!-- start -->')
                lines.append(f'  <circle cx="{tx(ext[-1].x2):.2f}" cy="{ty(ext[-1].y2):.2f}" '
                             f'r="{r}" fill="#DC2626" opacity="0.8"/>  <!-- end -->')

        lines.append('</svg>')
        return "\n".join(lines)

    def _seg(self, s, tx, ty):
        if s.is_arc:
            return self._arc(s, tx, ty)
        return (f'    <line x1="{tx(s.x1):.2f}" y1="{ty(s.y1):.2f}" '
                f'x2="{tx(s.x2):.2f}" y2="{ty(s.y2):.2f}"/>')

    def _arc(self, s, tx, ty):
        r = s.r * self.scale
        sa = math.atan2(s.y1 - s.cy, s.x1 - s.cx)
        ea = math.atan2(s.y2 - s.cy, s.x2 - s.cx)
        sweep = (sa - ea) if s.clockwise else (ea - sa)
        if sweep < 0: sweep += 2 * math.pi
        large = 1 if sweep > math.pi else 0
        sf = 0 if s.clockwise else 1
        sf = 1 - sf  # flip for Y-axis inversion
        return (f'    <path d="M {tx(s.x1):.2f} {ty(s.y1):.2f} '
                f'A {r:.2f} {r:.2f} 0 {large} {sf} '
                f'{tx(s.x2):.2f} {ty(s.y2):.2f}"/>')

    @staticmethod
    def _empty_svg():
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50">'
                '<text x="10" y="30" font-size="14" fill="#666">'
                'No toolpath data found.</text></svg>')


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert G-code files to SVG toolpath visualizations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s square.gcode                    Basic conversion
  %(prog)s square.gcode -o path.svg        Specify output file
  %(prog)s square.gcode --show-travel      Show travel moves as dashed lines
  %(prog)s square.gcode --show-points      Mark start/end points
  %(prog)s square.gcode --all-moves        Render ALL moves, not just extrusion
  %(prog)s square.gcode --scale 4          Enlarge output 4×
  %(prog)s *.gcode                         Batch convert multiple files
""",
    )
    parser.add_argument("files", nargs="+", metavar="FILE",
                        help="G-code file(s) to convert")
    parser.add_argument("-o", "--output", metavar="SVG",
                        help="Output SVG path (single file only)")
    parser.add_argument("--scale", type=float, default=2.0,
                        help="Scale factor (default: 2.0)")
    parser.add_argument("--stroke", type=float, default=STROKE_WIDTH,
                        help=f"Stroke width in px (default: {STROKE_WIDTH})")
    parser.add_argument("--show-travel", action="store_true",
                        help="Show non-extrusion travel moves")
    parser.add_argument("--show-points", action="store_true",
                        help="Mark start (green) and end (red) points")
    parser.add_argument("--all-moves", action="store_true",
                        help="Render all XY moves, not just extrusion")
    parser.add_argument("--bg", default="#FFFFFF", metavar="COLOR",
                        help="Background color (default: #FFFFFF)")

    args = parser.parse_args()

    if args.output and len(args.files) > 1:
        print("Error: --output only works with a single input file.", file=sys.stderr)
        sys.exit(1)

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"Warning: '{filepath}' not found, skipping.", file=sys.stderr)
            continue

        gparser = GCodeParser(all_moves=(args.all_moves or args.show_travel))
        segments = gparser.parse_file(filepath)

        ext_count = sum(1 for s in segments if s.extruding)
        travel_count = sum(1 for s in segments if not s.extruding)
        layers = max((s.layer for s in segments), default=0) + 1

        renderer = SVGRenderer(
            segments,
            scale=args.scale,
            stroke_width=args.stroke,
            show_travel=args.show_travel,
            show_points=args.show_points,
            background=args.bg,
        )
        svg_content = renderer.render()

        out_path = args.output if args.output else str(Path(filepath).with_suffix(".svg"))
        with open(out_path, "w") as f:
            f.write(svg_content)

        print(f"✓ {filepath}")
        print(f"  → {out_path}")
        print(f"  {ext_count} extrusion segments, {travel_count} travel moves, {layers} layer(s)")


if __name__ == "__main__":
    main()
