# vexcel_masker

A small, readable Python library to pull **Vexcel** imagery (oblique, ortho, DSM)
and **mask** it to a property boundary or a building footprint.

The hard part it solves: an **oblique** (angled) aerial photo is a perspective
view, so a tall neighbour leans across the property line. You can't just draw the
parcel outline on the image. This library shoots a ray from every pixel, finds
the first ground/roof it hits using the DSM height map, and keeps the pixel only
if that hit point is really inside the parcel. (For **ortho** images, which are
already flattened onto the ground, masking is a simple polygon rasterise.)

## What's inside (3 small files)

| file | what it does |
|------|--------------|
| [`vexcel_masker/api.py`](vexcel_masker/api.py) | log in and fetch data: `get_dsm`, `get_ortho`, `get_oriented`, `get_parcel`, `get_structures`, `best_collection` |
| [`vexcel_masker/camera.py`](vexcel_masker/camera.py) | the aerial-camera geometry: project world↔pixel, and `solve_camera` (auto-detects the camera's angle convention) |
| [`vexcel_masker/masking.py`](vexcel_masker/masking.py) | the `DSM` height-map + ray-caster, and `mask_oblique` / `mask_ortho` |

Everything is heavily commented so it can be handed to someone new.

## Setup

1. **Install** (pick one):
   ```bash
   conda env create -f environment.yml && conda activate vexcel-masker
   # or
   pip install -r requirements.txt
   ```
2. **Credentials**: copy `config.example.ini` to `config.ini` and fill in your
   Vexcel username and password. (`config.ini` is git-ignored.)

## Use it

```python
import vexcel_masker as vm

token = vm.get_token_from_config("config.ini")     # log in once
lon, lat = -76.876653, 38.757577                    # x, y in degrees

parcel     = vm.get_parcel(token, lon, lat)         # property boundary
structures = vm.get_structures(token, lon, lat)     # building footprints

coll  = vm.best_collection(token, lon, lat)         # one flight w/ all layers
dsm   = vm.get_dsm(token, lon, lat, collection=coll)
ortho = vm.get_ortho(token, lon, lat, collection=coll)
north = vm.get_oriented(token, lon, lat, "north", collection=coll)

# oblique, masked to the parcel (everything else painted magenta)
vm.show(vm.mask_oblique(north, dsm, parcel, fill="magenta"))

# oblique, masked to just the buildings (fill = the image's average colour)
vm.show(vm.mask_oblique(north, dsm, structures, fill="average"))

# ortho, masked to the parcel (fill = black), then saved to disk
vm.save(vm.mask_ortho(ortho, parcel, fill="black"), "ortho_parcel.png")

# OR: just draw the mask BORDER on the real image (nothing hidden) to check fit
vm.show(vm.outline_oblique(north, dsm, parcel))               # default magenta line
vm.show(vm.outline_ortho(ortho, structures, color="cyan"))
```

### Options

* **Mask vs. outline**: `mask_oblique` / `mask_ortho` hide everything outside the
  polygon; `outline_oblique` / `outline_ortho` instead draw just the boundary
  **line** on the untouched image (default colour magenta, `thickness=` px) so
  you can verify the fit from a single picture.
* **What to mask to**: pass a **parcel** polygon or the **structures** list to
  any of the four functions.
* **Dilate**: `dilate=5` grows the polygon outward by **5 feet** before
  masking/outlining (negative shrinks it); default `0`. The buffer is measured in
  true ground feet. Works on all four functions, e.g.
  `vm.outline_oblique(north, dsm, structures, dilate=5)`.
* **Fill colour**: `fill="magenta"` (also `black`, `cyan`, `green`, `white`,
  `red`), or an `(R, G, B)` tuple, or `fill="average"` (the mean colour of the
  image — blends the mask into the scene).
* **Same-day layers**: `best_collection(...)` returns the most recent flight that
  has the oblique, DSM **and** ortho together, so all three match in date. Pass it
  as `collection=` to each `get_*` call.
* **Directions**: `get_oriented(..., "north" | "south" | "east" | "west")`.
* **Zoom / size**: `get_oriented(..., downsample=0)` is full native resolution
  (1 = half, 2 = quarter); `radius_m` sets the crop box. `get_dsm`/`get_ortho`
  take `size_m`.

## Demo

Open [`demo.ipynb`](demo.ipynb) and run it top to bottom. It walks through one
location in detail, then loops over a set of test points, saving masked oblique
and ortho images for both the parcel and the building footprints.

## Notes

* Data lives in Vexcel's **`urban`** layer (oblique, DSM and ortho together).
* The DSM's height datum is assumed to match the camera; that holds for these
  collections but is worth confirming for a new area.
* Auth quirk: the v2 API needs the token in the `Authorization: Bearer` header —
  the library does this for you.
