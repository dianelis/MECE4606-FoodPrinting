#!/usr/bin/env python3
"""
generate_gingerbread_house.py — Generate G-code for a dual-material food-printed gingerbread house.

Prints each house piece flat on the bed:
  - T0 (cookie dough): 4 equal walls, 2 roof panels — solid infill with perimeters
  - T1 (icing):        decorative top layer on each piece — windows, door, ridge line

Pieces are spaced on the bed so they all fit in one print job.
Each piece is printed independently: perimeter(s) then infill with T0,
then icing decorations on top with T1.

Usage:
    python generate_gingerbread_house.py
    python generate_gingerbread_house.py --wall-w 80 --wall-h 60 --layers 4
    python generate_gingerbread_house.py --help
"""

import argparse
import math
import os

# ─── Defaults ─────────────────────────────────────────────────────────────────

# Piece dimensions (mm) — all pieces printed flat (XY plane)
WALL_W          = 80.0    # wall width
WALL_H          = 60.0    # wall height
ROOF_W          = 90.0    # roof panel width (slightly wider for overhang)
ROOF_H          = 70.0    # roof panel height

# Cookie thickness (number of layers)
NUM_LAYERS      = 3       # vertical layers of cookie dough
LAYER_HEIGHT    = 3.0     # mm per layer (thicker for food)
FIRST_Z         = 3.0     # first layer Z height

# Icing layer (one pass on top of cookie layers)
ICING_Z_OFFSET  = 1.5     # mm above top cookie layer for icing

# Print bed layout — pieces arranged in a grid
BED_ORIGIN_X    = 20.0
BED_ORIGIN_Y    = 20.0
PIECE_GAP       = 15.0    # gap between pieces on bed

# Infill
INFILL_SPACING  = 5.0     # mm between infill lines
NUM_PERIMETERS  = 2       # perimeter passes per piece

# Print parameters
COOKIE_SPEED    = 800     # mm/min — slower for thick dough
ICING_SPEED     = 400     # mm/min — slow for fine detail
TRAVEL_SPEED    = 2000    # mm/min
LAYER_SPEED     = 600     # mm/min for layer transitions

# Extrusion
E_MULT_COOKIE   = 0.12    # extrusion per mm of travel (cookie)
E_MULT_ICING    = 0.06    # extrusion per mm of travel (icing — thinner)
RETRACT         = 2.0     # mm retraction
Z_HOP           = 2.0     # mm z-hop on travel

# Tool IDs
T_COOKIE        = 0
T_ICING         = 1

# Decoration sizes (relative to piece, as fractions)
WINDOW_SIZE     = 12.0    # mm square window
DOOR_W          = 14.0    # mm door width
DOOR_H          = 22.0    # mm door height


# ─── Geometry Helpers ─────────────────────────────────────────────────────────

def seg_length(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def rect_perimeter(x, y, w, h):
    """Return corner points of a rectangle (closed loop)."""
    return [
        (x,     y),
        (x + w, y),
        (x + w, y + h),
        (x,     y + h),
        (x,     y),
    ]


def rect_infill_lines(x, y, w, h, spacing, angle_deg=0):
    """Generate infill lines across a rectangle at a given angle.
    Returns list of line segments: each segment is [(x1,y1),(x2,y2)].
    Alternates direction for continuous travel.
    """
    if angle_deg == 0:
        lines = []
        cur_y = y + spacing
        row = 0
        while cur_y < y + h - spacing * 0.5:
            if row % 2 == 0:
                lines.append([(x + spacing * 0.3, cur_y), (x + w - spacing * 0.3, cur_y)])
            else:
                lines.append([(x + w - spacing * 0.3, cur_y), (x + spacing * 0.3, cur_y)])
            cur_y += spacing
            row += 1
        return lines
    else:
        # Rotated infill: project bounding box, clip to rect
        rad = math.radians(angle_deg)
        cx, cy = x + w / 2, y + h / 2
        diag = math.hypot(w, h)
        lines = []
        t = -diag
        row = 0
        while t < diag:
            # Line perpendicular to infill direction
            dx = math.cos(rad + math.pi / 2)
            dy = math.sin(rad + math.pi / 2)
            # Sample many points along the fill line
            px0 = cx + t * dx - diag * math.cos(rad)
            py0 = cy + t * dy - diag * math.sin(rad)
            px1 = cx + t * dx + diag * math.cos(rad)
            py1 = cy + t * dy + diag * math.sin(rad)
            # Clip to rectangle (simple parametric clip)
            clipped = clip_line_to_rect(px0, py0, px1, py1, x, y, x + w, y + h)
            if clipped:
                if row % 2 == 1:
                    clipped = [clipped[1], clipped[0]]
                lines.append(clipped)
            t += spacing
            row += 1
        return lines


def clip_line_to_rect(x0, y0, x1, y1, rxmin, rymin, rxmax, rymax):
    """Liang-Barsky clipping. Returns [(x0,y0),(x1,y1)] or None."""
    dx, dy = x1 - x0, y1 - y0
    p = [-dx, dx, -dy, dy]
    q = [x0 - rxmin, rxmax - x0, y0 - rymin, rymax - y0]
    t0, t1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
        elif pi < 0:
            t0 = max(t0, qi / pi)
        else:
            t1 = min(t1, qi / pi)
    if t0 > t1:
        return None
    return [(x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)]


# ─── Decoration Paths ─────────────────────────────────────────────────────────

def window_path(cx, cy, size):
    """Square window outline + cross."""
    half = size / 2
    x0, y0 = cx - half, cy - half
    x1, y1 = cx + half, cy + half
    outer = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    cross_h = [(x0, cy), (x1, cy)]
    cross_v = [(cx, y0), (cx, y1)]
    return [outer, cross_h, cross_v]

def door_path(cx, by, w, h):
    """Door outline: rectangular with arched top."""
    x0 = cx - w / 2
    x1 = cx + w / 2
    arch_r = w / 2
    arch_pts = []
    for i in range(13):
        angle = math.pi - math.pi * i / 12
        ax = cx + arch_r * math.cos(angle)
        ay = (by + h - arch_r) + arch_r * math.sin(angle)
        arch_pts.append((ax, ay))
    outline = [(x0, by), (x0, by + h - arch_r)] + arch_pts + [(x1, by + h - arch_r), (x1, by), (x0, by)]
    return [outline]

def roof_ridge_path(x, y, w, h):
    """Simple dotted ridge line along the top of a roof panel."""
    cy = y + h * 0.15
    # Dashed: 5mm segments every 10mm
    segs = []
    xc = x + 5
    while xc + 4 < x + w:
        segs.append([(xc, cy), (xc + 4, cy)])
        xc += 10
    return segs

def snowflake_paths(cx, cy, r):
    """6-spoke snowflake (icing detail for roof)."""
    segs = []
    for i in range(6):
        angle = math.pi * i / 3
        ex = cx + r * math.cos(angle)
        ey = cy + r * math.sin(angle)
        segs.append([(cx, cy), (ex, ey)])
        # small cross-tick at 2/3
        mx = cx + (r * 0.65) * math.cos(angle)
        my = cy + (r * 0.65) * math.sin(angle)
        pa = angle + math.pi / 2
        segs.append([
            (mx - 3 * math.cos(pa), my - 3 * math.sin(pa)),
            (mx + 3 * math.cos(pa), my + 3 * math.sin(pa))
        ])
    return segs


# ─── G-code Generator ─────────────────────────────────────────────────────────

class GingerbreadGenerator:
    def __init__(self, *, wall_w, wall_h, roof_w, roof_h,
                 num_layers, layer_height, first_z, icing_z_offset,
                 infill_spacing, num_perimeters,
                 cookie_speed, icing_speed, travel_speed,
                 e_mult_cookie, e_mult_icing,
                 retract, z_hop,
                 bed_origin_x, bed_origin_y, piece_gap):

        self.wall_w         = wall_w
        self.wall_h         = wall_h
        self.roof_w         = roof_w
        self.roof_h         = roof_h
        self.num_layers     = num_layers
        self.layer_height   = layer_height
        self.first_z        = first_z
        self.icing_z_offset = icing_z_offset
        self.infill_spacing = infill_spacing
        self.num_perimeters = num_perimeters
        self.cookie_speed   = cookie_speed
        self.icing_speed    = icing_speed
        self.travel_speed   = travel_speed
        self.e_mult_cookie  = e_mult_cookie
        self.e_mult_icing   = e_mult_icing
        self.retract        = retract
        self.z_hop          = z_hop

        self.lines          = []
        self.e_total        = 0.0
        self.current_z      = 0.0
        self.current_tool   = None
        self._retracted     = False

        # Compute piece origins (laid out on bed in 2 rows of 3)
        # Row 0: wall1, wall2, wall3
        # Row 1: wall4, roof1, roof2
        ox, oy = bed_origin_x, bed_origin_y
        self.pieces = [
            # (label, x-origin, y-origin, width, height, piece_type)
            ("Wall 1 (front)",  ox,                              oy,                              wall_w, wall_h, "wall"),
            ("Wall 2 (back)",   ox + wall_w + piece_gap,         oy,                              wall_w, wall_h, "wall"),
            ("Wall 3 (left)",   ox + 2*(wall_w + piece_gap),     oy,                              wall_w, wall_h, "wall"),
            ("Wall 4 (right)",  ox,                              oy + wall_h + piece_gap,         wall_w, wall_h, "wall"),
            ("Roof Panel 1",    ox + wall_w + piece_gap,         oy + wall_h + piece_gap,         roof_w, roof_h, "roof"),
            ("Roof Panel 2",    ox + wall_w + piece_gap + roof_w + piece_gap, oy + wall_h + piece_gap, roof_w, roof_h, "roof"),
        ]

    # ── Output helpers ──

    def _emit(self, line):
        self.lines.append(line)

    def _extrude_move(self, x, y, speed, e_mult):
        """Move to (x,y) with extrusion."""
        d = seg_length(self.cx, self.cy, x, y)
        if d < 0.001:
            return
        self.e_total += d * e_mult
        self._emit(f"G1 X{x:.3f} Y{y:.3f} E{self.e_total:.4f} F{speed}")
        self.cx, self.cy = x, y

    def _travel(self, x, y):
        """Travel move with z-hop and retract."""
        # Retract
        if not self._retracted:
            self.e_total -= self.retract
            self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}  ; retract")
            self._retracted = True
        # Z-hop
        self._emit(f"G1 Z{self.current_z + self.z_hop:.2f} F600  ; z-hop")
        # XY travel
        self._emit(f"G1 X{x:.3f} Y{y:.3f} F{self.travel_speed}  ; travel")
        # Lower
        self._emit(f"G1 Z{self.current_z:.2f} F600  ; lower")
        # Prime
        self.e_total += self.retract
        self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}  ; prime")
        self._retracted = False
        self.cx, self.cy = x, y

    def _set_z(self, z):
        self.current_z = z
        self._emit(f"G1 Z{z:.2f} F600  ; set layer Z")

    def _tool_change(self, tool):
        if tool == self.current_tool:
            return
        # Retract current tool
        if not self._retracted and self.current_tool is not None:
            self.e_total -= self.retract
            self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}  ; retract before tool change")
            self._retracted = True
        self._emit(f"")
        self._emit(f"T{tool}  ; switch to {'cookie dough' if tool == T_COOKIE else 'icing'} extruder")
        self._emit(f"G92 E0  ; reset extruder after tool change")
        self.e_total = 0.0
        self.current_tool = tool
        self._retracted = True

    # ── Cookie layer (T0) ──

    def _print_cookie_layer(self, x, y, w, h, z, layer_idx):
        """Print one cookie layer: perimeters then rectilinear infill."""
        self._set_z(z)
        angle = 45 if layer_idx % 2 == 0 else 135  # alternate infill angle

        # Perimeters (outermost first)
        for peri in range(self.num_perimeters):
            inset = peri * (self.infill_spacing * 0.4)
            pts = rect_perimeter(x + inset, y + inset, w - 2 * inset, h - 2 * inset)
            self._travel(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                self._extrude_move(px, py, self.cookie_speed, self.e_mult_cookie)

        # Infill
        inset = self.num_perimeters * self.infill_spacing * 0.4
        lines = rect_infill_lines(x + inset, y + inset, w - 2 * inset, h - 2 * inset,
                                  self.infill_spacing, angle_deg=angle)
        for seg in lines:
            self._travel(seg[0][0], seg[0][1])
            self._extrude_move(seg[1][0], seg[1][1], self.cookie_speed, self.e_mult_cookie)

    # ── Icing decorations (T1) ──

    def _print_paths(self, path_list, speed, e_mult):
        """Print a list of paths (each path is a list of points)."""
        for path in path_list:
            if len(path) < 2:
                continue
            self._travel(path[0][0], path[0][1])
            for px, py in path[1:]:
                self._extrude_move(px, py, speed, e_mult)

    def _print_wall_icing(self, x, y, w, h, z, label):
        """Icing decorations for a wall piece."""
        self._set_z(z)

        # Outline border
        border_inset = 3.0
        outline = rect_perimeter(x + border_inset, y + border_inset,
                                 w - 2 * border_inset, h - 2 * border_inset)
        self._print_paths([outline], self.icing_speed, self.e_mult_icing)

        is_front = "front" in label.lower()

        if is_front:
            # Door (centered bottom)
            door_cx = x + w / 2
            door_by = y + 6
            door_paths = door_path(door_cx, door_by, DOOR_W, DOOR_H)
            self._print_paths(door_paths, self.icing_speed, self.e_mult_icing)

            # Two windows (upper left and upper right)
            for wx_offset in [0.25, 0.75]:
                wcx = x + w * wx_offset
                wcy = y + h * 0.68
                self._print_paths(window_path(wcx, wcy, WINDOW_SIZE),
                                  self.icing_speed, self.e_mult_icing)
        else:
            # Side/back walls: single centered window
            wcx = x + w / 2
            wcy = y + h * 0.6
            self._print_paths(window_path(wcx, wcy, WINDOW_SIZE),
                               self.icing_speed, self.e_mult_icing)

    def _print_roof_icing(self, x, y, w, h, z):
        """Icing decorations for a roof piece: outline, ridge line, snowflakes."""
        self._set_z(z)

        # Outline
        border_inset = 3.0
        outline = rect_perimeter(x + border_inset, y + border_inset,
                                 w - 2 * border_inset, h - 2 * border_inset)
        self._print_paths([outline], self.icing_speed, self.e_mult_icing)

        # Ridge dots along top edge
        ridge = roof_ridge_path(x, y, w, h)
        self._print_paths(ridge, self.icing_speed, self.e_mult_icing)

        # Two snowflakes
        for cx_frac in [0.3, 0.7]:
            sf = snowflake_paths(x + w * cx_frac, y + h * 0.55, 8.0)
            self._print_paths(sf, self.icing_speed, self.e_mult_icing)

    # ── Main generate ──

    def generate(self) -> str:
        self._header()
        self._init_block()

        # ── Phase 1: Print all cookie layers (T0) ──
        self._emit("")
        self._emit("; ================================================================")
        self._emit("; PHASE 1: COOKIE DOUGH (T0) — all pieces, all layers")
        self._emit("; ================================================================")
        self._tool_change(T_COOKIE)

        for layer_idx in range(self.num_layers):
            z = self.first_z + layer_idx * self.layer_height
            self._emit("")
            self._emit(f"; --- Cookie layer {layer_idx + 1}/{self.num_layers} (Z={z:.1f}mm) ---")

            for label, px, py, pw, ph, ptype in self.pieces:
                self._emit(f"; Piece: {label}")
                self._print_cookie_layer(px, py, pw, ph, z, layer_idx)

        # ── Phase 2: Icing decorations (T1) ──
        self._emit("")
        self._emit("; ================================================================")
        self._emit("; PHASE 2: ICING (T1) — decorations on top of each piece")
        self._emit("; ================================================================")
        self._tool_change(T_ICING)

        icing_z = self.first_z + (self.num_layers - 1) * self.layer_height + self.icing_z_offset

        self._emit(f"; Icing layer Z={icing_z:.1f}mm")
        self._set_z(icing_z)

        for label, px, py, pw, ph, ptype in self.pieces:
            self._emit(f"")
            self._emit(f"; Icing: {label}")
            if ptype == "wall":
                self._print_wall_icing(px, py, pw, ph, icing_z, label)
            else:
                self._print_roof_icing(px, py, pw, ph, icing_z)

        self._finish_block()
        return "\n".join(self.lines) + "\n"

    def _header(self):
        top_z = self.first_z + (self.num_layers - 1) * self.layer_height + self.icing_z_offset
        self._emit("; ================================================================")
        self._emit("; GINGERBREAD HOUSE — Dual-Material Food Print G-code")
        self._emit("; ================================================================")
        self._emit(";")
        self._emit("; T0 = Cookie dough (walls + roof — all layers)")
        self._emit("; T1 = Icing        (decorations on top layer)")
        self._emit(";")
        self._emit(f"; Pieces: 4 walls ({self.wall_w:.0f}x{self.wall_h:.0f}mm) + 2 roof panels ({self.roof_w:.0f}x{self.roof_h:.0f}mm)")
        self._emit(f"; Cookie layers: {self.num_layers}  x  {self.layer_height:.1f}mm = {self.num_layers*self.layer_height:.1f}mm thick")
        self._emit(f"; Total print height: {top_z:.1f}mm")
        self._emit(f"; Perimeters per layer: {self.num_perimeters}")
        self._emit(f"; Infill spacing: {self.infill_spacing:.1f}mm  (alternating 45°/135°)")
        self._emit(f"; Cookie speed: {self.cookie_speed} mm/min  |  Icing speed: {self.icing_speed} mm/min")
        self._emit(";")
        self._emit("; Piece layout on bed:")
        for label, px, py, pw, ph, ptype in self.pieces:
            self._emit(f";   {label:20s} origin=({px:.0f},{py:.0f})  size={pw:.0f}x{ph:.0f}mm")
        self._emit(";")
        self._emit("; Icing decorations:")
        self._emit(";   Wall 1 (front) : outline, arched door, 2 windows")
        self._emit(";   Walls 2-4      : outline, 1 window each")
        self._emit(";   Roof panels    : outline, ridge line, 2 snowflakes each")
        self._emit(";")
        self._emit("; Assembly after printing:")
        self._emit(";   1. Let pieces cool/set flat")
        self._emit(";   2. Join walls at 90° with extra icing")
        self._emit(";   3. Attach roof panels at ~45° ridge angle")
        self._emit("; ================================================================")
        self._emit("")

    def _init_block(self):
        self._emit("; === INITIALIZATION ===")
        self._emit("G21              ; millimeters")
        self._emit("G90              ; absolute positioning")
        self._emit("M82              ; absolute extrusion")
        self._emit("G28              ; home all axes")
        self._emit("G92 E0           ; zero extruder")
        # Initialize position tracking
        self.cx, self.cy = 0.0, 0.0
        self._emit("")

    def _finish_block(self):
        # Final retract
        if not self._retracted:
            self.e_total -= self.retract
            self._emit(f"G1 E{self.e_total:.4f} F{self.travel_speed}  ; final retract")
        self._emit("")
        self._emit("; === FINISH ===")
        self._emit(f"G1 Z{self.current_z + 30:.1f} F600   ; lift nozzle")
        self._emit(f"G1 X0 Y0 F{self.travel_speed}        ; park")
        self._emit("M84              ; disable motors")
        self._emit("")
        self._emit("; === END ===")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate dual-material gingerbread house G-code for food printing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Prints 6 pieces flat on the bed (4 walls + 2 roof panels).
T0 = cookie dough (all structural layers)
T1 = icing (top decorative layer: windows, door, snowflakes)

Assembly: join walls with extra icing after printing.

Examples:
  %(prog)s                              Default 80x60mm walls
  %(prog)s --wall-w 100 --wall-h 70     Larger house
  %(prog)s --layers 4 --layer-height 4  Thicker cookie
  %(prog)s --icing-speed 300            Slower icing for finer detail
""",
    )
    parser.add_argument("--wall-w",       type=float, default=WALL_W,       help=f"Wall width mm (default: {WALL_W})")
    parser.add_argument("--wall-h",       type=float, default=WALL_H,       help=f"Wall height mm (default: {WALL_H})")
    parser.add_argument("--roof-w",       type=float, default=ROOF_W,       help=f"Roof panel width mm (default: {ROOF_W})")
    parser.add_argument("--roof-h",       type=float, default=ROOF_H,       help=f"Roof panel height mm (default: {ROOF_H})")
    parser.add_argument("--layers",       type=int,   default=NUM_LAYERS,   help=f"Cookie layers (default: {NUM_LAYERS})")
    parser.add_argument("--layer-height", type=float, default=LAYER_HEIGHT, help=f"Layer height mm (default: {LAYER_HEIGHT})")
    parser.add_argument("--perimeters",   type=int,   default=NUM_PERIMETERS,help=f"Perimeter passes (default: {NUM_PERIMETERS})")
    parser.add_argument("--infill",       type=float, default=INFILL_SPACING,help=f"Infill line spacing mm (default: {INFILL_SPACING})")
    parser.add_argument("--cookie-speed", type=int,   default=COOKIE_SPEED, help=f"Cookie print speed mm/min (default: {COOKIE_SPEED})")
    parser.add_argument("--icing-speed",  type=int,   default=ICING_SPEED,  help=f"Icing print speed mm/min (default: {ICING_SPEED})")
    parser.add_argument("--e-cookie",     type=float, default=E_MULT_COOKIE,help=f"Cookie extrusion multiplier (default: {E_MULT_COOKIE})")
    parser.add_argument("--e-icing",      type=float, default=E_MULT_ICING, help=f"Icing extrusion multiplier (default: {E_MULT_ICING})")
    parser.add_argument("-o", "--output", default=None, help="Output .gcode file path")

    args = parser.parse_args()

    gen = GingerbreadGenerator(
        wall_w=args.wall_w,     wall_h=args.wall_h,
        roof_w=args.roof_w,     roof_h=args.roof_h,
        num_layers=args.layers, layer_height=args.layer_height,
        first_z=FIRST_Z,        icing_z_offset=ICING_Z_OFFSET,
        infill_spacing=args.infill,
        num_perimeters=args.perimeters,
        cookie_speed=args.cookie_speed,
        icing_speed=args.icing_speed,
        travel_speed=TRAVEL_SPEED,
        e_mult_cookie=args.e_cookie,
        e_mult_icing=args.e_icing,
        retract=RETRACT,        z_hop=Z_HOP,
        bed_origin_x=BED_ORIGIN_X,
        bed_origin_y=BED_ORIGIN_Y,
        piece_gap=PIECE_GAP,
    )

    gcode = gen.generate()

    if args.output:
        out_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(script_dir, "gingerbread_house.gcode")

    with open(out_path, "w") as f:
        f.write(gcode)

    thickness = FIRST_Z + (args.layers - 1) * args.layer_height + ICING_Z_OFFSET
    print(f"✓ Generated: {out_path}")
    print(f"  6 pieces: 4 walls ({args.wall_w:.0f}x{args.wall_h:.0f}mm) + 2 roof panels ({args.roof_w:.0f}x{args.roof_h:.0f}mm)")
    print(f"  Cookie: {args.layers} layers x {args.layer_height:.1f}mm = {args.layers*args.layer_height:.1f}mm thick")
    print(f"  Total piece height: {thickness:.1f}mm")
    print(f"  T0 (cookie dough): perimeter + {args.infill:.0f}mm infill @ {args.cookie_speed} mm/min")
    print(f"  T1 (icing): windows, door, snowflakes @ {args.icing_speed} mm/min")
    print(f"")
    print(f"  Bed layout (left→right, bottom→top):")
    print(f"    Row 1: Wall 1, Wall 2, Wall 3")
    print(f"    Row 2: Wall 4, Roof Panel 1, Roof Panel 2")


if __name__ == "__main__":
    main()
