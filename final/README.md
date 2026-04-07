# Final Fort

This folder contains a circular "fort" pattern built in the same spirit as the
`spirograph` generators: Python code computes `x, y, z` paths and emits
food-printing G-code.

Files:

- `generate_final_fort_v1.py`
  Creates two separate toolpaths:
  - `di2256_final_fort_outline_v1.gcode`
  - `di2256_final_fort_fill_v1.gcode`

What gets generated:

- `outline`: a crenellated circular wall that looks like a small fort
- `fill`: concentric circular rings that stay inside the fort wall

Run:

```bash
python3 final/generate_final_fort_v1.py
```

Useful options:

```bash
python3 final/generate_final_fort_v1.py --layers 4 --battlements 20
python3 final/generate_final_fort_v1.py --radius 30 --ring-step 3.5
```
