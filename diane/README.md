# Diane Fort

This folder contains a circular "fort" pattern built in the same spirit as the
`spirograph` generators: Python code computes `x, y, z` paths and emits
food-printing G-code.

Files:

- `generate_diane_fort_v1.py`
  Creates two separate toolpaths:
  - `di2256_diane_fort_outline_v1.gcode`
  - `di2256_diane_fort_fill_v1.gcode`
- `generate_diane_fort_v2.py`
  Creates two separate toolpaths:
  - `di2256_diane_fort_outline_v2.gcode`
  - `di2256_diane_fort_fill_v2.gcode`

What gets generated:

- `outline`: a crenellated circular wall that looks like a small fort
- `fill`: concentric circular rings that stay inside the fort wall
- `v2 outline`: a short fort base with a tall circular tower stacked above it
- `v2 fill`: matching stacked fill rings for the base and tower

Run:

```bash
python3 diane/generate_diane_fort_v1.py
python3 diane/generate_diane_fort_v2.py
```

Useful options:

```bash
python3 diane/generate_diane_fort_v1.py --layers 4 --battlements 20
python3 diane/generate_diane_fort_v1.py --radius 30 --ring-step 3.5
python3 diane/generate_diane_fort_v2.py --tower-layers 20 --first-z 2
python3 diane/generate_diane_fort_v2.py --base-layers 4 --tower-radius 14
```
