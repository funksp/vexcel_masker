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

## How the oblique masking works

### The simple version (for anyone)

An **oblique** photo is taken from an angle, not straight down. That angle is
useful (you can see the sides of houses), but it plays a trick: tall things
**lean**. A neighbour's two-storey house leans over into the photo and *appears*
to sit on top of ground that isn't theirs. So if we just drew the property lines
flat onto the photo, we'd accidentally scoop up the neighbour's roof.

To avoid that, we don't work in the flat photo — we figure out, for **every dot
in the photo, which real spot on the ground it is actually showing.** Picture
shining a laser from the camera out through each dot until it lands on a 3-D
model of the neighbourhood (we have one — it's a height map called a DSM).
Wherever the laser lands is the true spot that dot is looking at. Then we ask one
question: *is that spot inside the property?* If yes, keep the dot; if no, hide it.

Because the laser stops at the **first** thing it touches, blocked views take
care of themselves: if a neighbour's roof is in the way of the backyard, the
laser hits the roof (which is the neighbour's), so we correctly hide it instead
of pretending we can see the yard behind it.

> **In one line:** for every pixel we trace where it really lands on the ground,
> and keep it only if that ground is inside the property — so leaning neighbours
> and blocked views are handled automatically.

For a straight-down **ortho** image none of this is needed: it's already been
flattened onto the ground like a map, so we can lay the property outline straight
onto it.

### The slightly more technical version

An oblique is a **perspective projection of a 3-D scene**, so there is no single
scale (GSD) that maps the whole image to the ground — near things are big, far
things small, tall things shift. That rules out the flat, affine "draw the
polygon on the image" approach that works for orthos.

So we do **backward ray-casting against a DSM**:

1. **Reconstruct the camera.** From Vexcel's per-image metadata we recover the
   camera's exact position and orientation, giving us, for any pixel, the precise
   3-D ray of light that produced it (`camera.py`).
2. **Trace each ray to the surface.** We march that ray through the DSM (a height
   map of ground, roofs and trees) until it first crosses the surface. That first
   intersection is the real `(X, Y, Z)` the pixel sees (`masking.py`,
   `DSM.first_hit`).
3. **Test the ground point.** Take the hit's `(X, Y)` and check it against the
   parcel or building polygon (point-in-polygon). Inside → keep, outside → mask.

Taking the **first** hit is what makes occlusion free: a roof blocking the yard
is struck first, so that pixel is tested as the roof's location (outside the
parcel) rather than the hidden yard. The result is a mask that respects real 3-D
geometry — tall neighbours leaning in are excluded, and surfaces truly inside the
parcel are kept, even where the perspective distorts them.

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
