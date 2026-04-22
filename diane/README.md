# Diane Prints

This directory groups Diane's multi-ingredient food-printing experiments.
Each subfolder contains a Python generator plus the emitted outline/fill G-code
for a two-material print.

## Layout

- `multi_ingredient_fort/`
  - `generate_diane_fort.py`
  - `di2256_fort_outline.gcode`
  - `di2256_fort_fill.gcode`
  - `di2256_fort_spirograph_topper.gcode`
- `multi_ingredient_spirograph/`
  - `generate_multi_ingredient_spirograph.py`
  - `di2256_spirograph_outline.gcode`
  - `di2256_spirograph_fill.gcode`

## What Each Generator Produces

- `outline`: the supporting structure printed with the first material
- `fill`: the interior printed with the second material

For both designs, the workflow is the same:

- layer 1 builds a solid base
- later layers trace the outer wall / silhouette
- the fill file stacks interior passes at the same height range, shifted upward
  to clear the outer wall during the material switch

The fort folder also includes a continuation file:

- `di2256_fort_spirograph_topper.gcode`: a 3-layer spirograph that starts above
  the final fort-fill height so it can be printed on top as the next stage

## Run

```bash
python3 diane/multi_ingredient_fort/generate_diane_fort.py
python3 diane/multi_ingredient_spirograph/generate_multi_ingredient_spirograph.py
```
