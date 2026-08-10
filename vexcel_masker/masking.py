"""
masking.py -- keep only the pixels that fall inside a parcel (or a building).

Two very different pictures, two very different masks:

* ORTHO  (mask_ortho)  -- an ortho image is already "flattened" onto the ground,
  like a map. A parcel polygon maps straight onto its pixels, so masking is just
  "rasterise the polygon". No 3-D needed.

* OBLIQUE (mask_oblique) -- an oblique photo is a tilted, perspective view. A
  tall neighbour leans across the property line, so you CANNOT just draw the
  polygon on the image. Instead, for every pixel we shoot its camera ray out
  into the world, find the first surface it hits using the DSM (a height map),
  and keep the pixel only if that hit point is inside the polygon on the ground.
  First-hit means a roof blocking the yard is handled automatically.

The `fill` argument decides what the masked-out area becomes: a named colour, an
(R, G, B) triple, or the string "average" (the mean colour of the whole image).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# =========================================================================== #
# Data containers
# =========================================================================== #
@dataclass
class DSM:
    """A digital surface model: a height (Z) for every ground (X, Y)."""

    data: np.ndarray            # 2-D array of elevations (metres); NaN = no data
    transform: object           # affine transform (pixel <-> world), from rasterio
    crs: str                    # e.g. "EPSG:32618" (the working UTM zone)

    @property
    def zmin(self):
        return float(np.nanmin(self.data))

    @property
    def cell_size(self):
        return float(abs(self.transform.a))

    def sample(self, X, Y):
        """Bilinear elevation at world (X, Y); NaN outside the raster."""
        inv = ~self.transform
        col = inv.a * X + inv.b * Y + inv.c - 0.5   # -> fractional pixel centre
        row = inv.d * X + inv.e * Y + inv.f - 0.5
        j0 = np.floor(col).astype(int); i0 = np.floor(row).astype(int)
        fj = col - j0; fi = row - i0
        h, w = self.data.shape
        out = np.full(np.shape(X), np.nan, float)
        acc = np.zeros(np.shape(X)); wsum = np.zeros(np.shape(X))
        for di, wi in ((0, 1 - fi), (1, fi)):
            for dj, wj in ((0, 1 - fj), (1, fj)):
                ii, jj = i0 + di, j0 + dj
                ok = (ii >= 0) & (ii < h) & (jj >= 0) & (jj < w)
                vals = np.where(ok, self.data[np.clip(ii, 0, h - 1), np.clip(jj, 0, w - 1)], np.nan)
                good = ok & np.isfinite(vals)
                acc = np.where(good, acc + wi * wj * np.where(good, vals, 0.0), acc)
                wsum = np.where(good, wsum + wi * wj, wsum)
        return np.where(wsum > 0, acc / np.where(wsum > 0, wsum, 1), out)

    def first_hit(self, origins, directions, step=None, max_steps=4000):
        """March rays and return the FIRST (X, Y, Z) where each enters the surface.

        Simple idea: walk along each ray in small steps. While the ray is above
        the ground (ray_z > surface_z) keep going; the step where it crosses to
        at/below the surface is the hit. We then refine it with a few bisections.
        Fully vectorised over all rays at once.
        """
        origins = np.atleast_2d(origins).astype(float)
        directions = np.atleast_2d(directions).astype(float)
        directions /= np.linalg.norm(directions, axis=1, keepdims=True)
        n = len(origins)
        if step is None:
            step = self.cell_size

        # limit marching to the ray span that is over the DSM's footprint
        s_enter, s_exit = _ray_box_span(origins, directions, self.transform, self.data.shape)
        hits = np.full((n, 3), np.nan)
        alive = np.isfinite(s_enter) & (s_exit > s_enter)
        if not alive.any():
            return hits, alive

        s = np.where(alive, np.clip(s_enter - step, 0, None), np.inf)
        prev_diff = np.full(n, np.nan)      # ray_z - surface_z at previous step
        prev_s = s.copy()
        lo = np.full(n, np.nan); hi = np.full(n, np.nan)   # bracket for refinement
        found = np.zeros(n, bool)

        for _ in range(max_steps):
            live = alive & ~found & (s <= s_exit + step)
            if not live.any():
                break
            P = origins[live] + s[live, None] * directions[live]
            diff = P[:, 2] - self.sample(P[:, 0], P[:, 1])
            idx = np.where(live)[0]
            crossed = np.isfinite(diff) & np.isfinite(prev_diff[idx]) & (prev_diff[idx] > 0) & (diff <= 0)
            hit_idx = idx[crossed]
            lo[hit_idx] = prev_s[idx][crossed]; hi[hit_idx] = s[idx][crossed]
            found[hit_idx] = True
            prev_diff[idx] = diff; prev_s[idx] = s[idx]
            s[idx[~crossed]] += step

        # refine each bracket [lo, hi] by bisection
        f = found
        if f.any():
            a, b = lo[f].copy(), hi[f].copy()
            o, d = origins[f], directions[f]
            for _ in range(20):
                m = 0.5 * (a + b)
                Pm = o + m[:, None] * d
                above = (Pm[:, 2] - self.sample(Pm[:, 0], Pm[:, 1])) > 0
                a = np.where(above, m, a)   # still above -> move the low end up
                b = np.where(above, b, m)   # now below   -> move the high end down
            m = 0.5 * (a + b)
            hits[f] = o + m[:, None] * d
        return hits, found


@dataclass
class Ortho:
    """A top-down ortho image with its geo-referencing."""

    image: np.ndarray           # (H, W, 3) uint8
    transform: object           # affine (pixel <-> world)
    crs: str                    # the ortho's CRS


# =========================================================================== #
# Fill colours
# =========================================================================== #
NAMED_COLORS = {
    "magenta": (255, 0, 255), "black": (0, 0, 0), "white": (255, 255, 255),
    "cyan": (0, 255, 255), "green": (0, 255, 0), "red": (255, 0, 0),
}


def resolve_fill(image, fill):
    """Turn a fill spec into an (R, G, B) uint8 triple.

    `fill` may be a name ("magenta"), an (R, G, B) tuple, or "average" (the mean
    colour of every pixel in the image).
    """
    if isinstance(fill, str):
        if fill == "average":
            return tuple(image.reshape(-1, 3).mean(axis=0).round().astype(int))
        if fill in NAMED_COLORS:
            return NAMED_COLORS[fill]
        raise ValueError(f"unknown fill colour {fill!r}")
    return tuple(int(c) for c in fill)


def _apply(image, keep, fill):
    """Keep real pixels where `keep` is True, else paint the fill colour."""
    out = image.copy()
    out[~keep] = np.array(resolve_fill(image, fill), np.uint8)
    return out


def _bbox(keep, margin, shape):
    """Pixel bounding box of the True region, padded by `margin`, clamped."""
    ys, xs = np.where(keep)
    y0 = max(0, ys.min() - margin); y1 = min(shape[0], ys.max() + 1 + margin)
    x0 = max(0, xs.min() - margin); x1 = min(shape[1], xs.max() + 1 + margin)
    return y0, y1, x0, x1


def _crop_and_apply(image, keep, fill, margin=15, zoom=True):
    """Paint the fill colour outside `keep`, and (if zoom) crop tight to `keep`.

    `zoom=True` (the default) trims the result to the kept region plus a small
    margin, so you see the parcel/building filling the frame instead of a tiny
    shape in a sea of fill colour.
    """
    if zoom and keep.any():
        y0, y1, x0, x1 = _bbox(keep, margin, image.shape)
        image, keep = image[y0:y1, x0:x1], keep[y0:y1, x0:x1]
    return _apply(image, keep, fill)


def _border(keep, thickness=2):
    """A boolean line marking the edge of the True region (numpy, no scipy)."""
    edge = np.zeros_like(keep)
    dv = keep[:-1, :] ^ keep[1:, :]      # vertical neighbours differ
    dh = keep[:, :-1] ^ keep[:, 1:]      # horizontal neighbours differ
    edge[:-1, :] |= dv; edge[1:, :] |= dv
    edge[:, :-1] |= dh; edge[:, 1:] |= dh
    for _ in range(max(0, thickness - 1)):           # thicken by 1px per extra step
        grow = edge.copy()
        grow[:-1, :] |= edge[1:, :]; grow[1:, :] |= edge[:-1, :]
        grow[:, :-1] |= edge[:, 1:]; grow[:, 1:] |= edge[:, :-1]
        edge = grow
    return edge


def _draw_outline(image, keep, color, thickness=2, zoom=True, margin=40):
    """Draw the mask's border on the real image (nothing is hidden)."""
    out = image.copy()
    out[_border(keep, thickness)] = np.array(resolve_fill(image, color), np.uint8)
    if zoom and keep.any():
        y0, y1, x0, x1 = _bbox(keep, margin, out.shape)
        out = out[y0:y1, x0:x1]
    return out


# =========================================================================== #
# The two masking operations
# =========================================================================== #
FEET_TO_METRES = 0.3048


def _to_working_polygon(polygon, dst_crs, dilate=0.0):
    """Accept a polygon or list of polygons (lon/lat) -> one geometry in dst_crs.

    `dilate` grows (or, if negative, shrinks) the polygon by that many **feet**.
    The buffer is done in a local UTM zone so the distance is true ground feet,
    then reprojected to `dst_crs` (correct even when `dst_crs` is Web Mercator).
    """
    from pyproj import Transformer
    from shapely.ops import transform, unary_union

    geoms = polygon if isinstance(polygon, (list, tuple)) else [polygon]
    merged = unary_union(list(geoms))               # lon/lat

    if dilate:
        c = merged.centroid
        zone = int((c.x + 180) / 6) + 1
        utm = f"EPSG:{(32600 if c.y >= 0 else 32700) + zone}"
        to_utm = Transformer.from_crs("EPSG:4326", utm, always_xy=True)
        from_utm = Transformer.from_crs(utm, "EPSG:4326", always_xy=True)
        m = transform(lambda x, y, z=None: to_utm.transform(x, y), merged)
        m = m.buffer(dilate * FEET_TO_METRES)       # feet -> metres, true ground distance
        merged = transform(lambda x, y, z=None: from_utm.transform(x, y), m)

    tf = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
    return transform(lambda x, y, z=None: tf.transform(x, y), merged)


def ortho_inside(ortho, polygon, dilate=0.0):
    """Boolean mask on the ortho grid: True where a pixel is inside the polygon.

    `dilate` grows/shrinks the polygon by that many feet before rasterising.
    """
    from rasterio.features import rasterize

    geom = _to_working_polygon(polygon, ortho.crs, dilate)
    h, w = ortho.image.shape[:2]
    return rasterize([(geom, 1)], out_shape=(h, w), transform=ortho.transform,
                     fill=0, dtype="uint8").astype(bool)


def mask_ortho(ortho, polygon, fill="magenta", dilate=0.0, zoom=True, margin=20):
    """Mask an ortho image to a parcel/structure polygon (lon/lat).

    `dilate` grows the polygon by that many feet (negative shrinks). `zoom=True`
    crops the result tight to the polygon; set it False to keep the whole tile.
    """
    inside = ortho_inside(ortho, polygon, dilate)
    return _crop_and_apply(ortho.image, inside, fill, margin=margin, zoom=zoom)


def outline_ortho(ortho, polygon, color="magenta", dilate=0.0, thickness=2, zoom=True, margin=40):
    """Draw the polygon's border on the ortho (no masking) so you can check fit.

    `dilate` grows/shrinks the polygon by that many feet before drawing.
    """
    inside = ortho_inside(ortho, polygon, dilate)
    return _draw_outline(ortho.image, inside, color, thickness, zoom, margin)


def _exterior_xy(geom):
    """All exterior-ring vertices of a (multi)polygon as x, y arrays."""
    xs, ys = [], []
    for g in getattr(geom, "geoms", [geom]):
        cx, cy = g.exterior.coords.xy
        xs += list(cx); ys += list(cy)
    return np.asarray(xs), np.asarray(ys)


def oblique_keep(oriented, dsm, polygon, dilate=0.0, ray_step=2, buffer_px=15, step=None):
    """Boolean mask (oriented.image size): True where the pixel's ground point is
    inside the polygon.

    For every pixel we find the ground point it actually sees (via DSM
    ray-casting) and test it against the polygon. To stay fast we (1) project the
    polygon to find the small image region it covers, (2) ray-cast that region on
    a grid every `ray_step` pixels, and (3) scale the result back up. Use
    `ray_step=1` for the most precise edges. `dilate` grows/shrinks the polygon
    by that many feet first.
    """
    import shapely

    geom = _to_working_polygon(polygon, dsm.crs, dilate)
    cam = oriented.camera
    h, w = oriented.image.shape[:2]
    keep = np.zeros((h, w), bool)

    # 1. where does the polygon land in this image? (drape its outline on the DSM)
    px, py = _exterior_xy(geom)
    pz = dsm.sample(px, py)
    pz = np.where(np.isfinite(pz), pz, dsm.zmin)
    pu, pv = cam.world_to_pixel(px, py, pz)
    good = np.isfinite(pu) & np.isfinite(pv)
    if not good.any():
        return keep
    u0 = max(0, int(np.min(pu[good])) - buffer_px); u1 = min(w, int(np.max(pu[good])) + buffer_px)
    v0 = max(0, int(np.min(pv[good])) - buffer_px); v1 = min(h, int(np.max(pv[good])) + buffer_px)
    if u1 <= u0 or v1 <= v0:
        return keep

    # 2. ray-cast a subsampled grid over just that region
    us = np.arange(u0, u1, ray_step); vs = np.arange(v0, v1, ray_step)
    uu, vv = np.meshgrid(us, vs)
    origins, dirs = cam.pixel_to_ray(uu.ravel(), vv.ravel())
    hits, ok = dsm.first_hit(origins, dirs, step=step)
    inside = np.zeros(len(hits), bool)
    hit_ok = ok & np.isfinite(hits[:, 0])
    if hit_ok.any():
        inside[hit_ok] = shapely.contains_xy(geom, hits[hit_ok, 0], hits[hit_ok, 1])
    grid = inside.reshape(uu.shape)

    # 3. scale the grid back up to full pixels and drop it into place
    block = np.repeat(np.repeat(grid, ray_step, 0), ray_step, 1)
    bh = min(block.shape[0], v1 - v0); bw = min(block.shape[1], u1 - u0)
    keep[v0:v0 + bh, u0:u0 + bw] = block[:bh, :bw]
    return keep


def mask_oblique(oriented, dsm, polygon, fill="magenta", dilate=0.0, zoom=True,
                 ray_step=2, buffer_px=15, step=None):
    """Mask an oblique image to a polygon: keep inside, paint `fill` outside.

    `dilate` grows the polygon by that many feet (negative shrinks). `zoom=True`
    (default) crops tight to the polygon; False keeps the whole crop.
    """
    keep = oblique_keep(oriented, dsm, polygon, dilate, ray_step, buffer_px, step)
    return _crop_and_apply(oriented.image, keep, fill, margin=buffer_px, zoom=zoom)


def outline_oblique(oriented, dsm, polygon, color="magenta", dilate=0.0, thickness=2,
                    zoom=True, margin=40, ray_step=2, buffer_px=15, step=None):
    """Draw the mask's border on the oblique (no masking) so you can check fit.

    Same geometry as `mask_oblique`, but instead of hiding the outside it strokes
    the boundary line onto the real image -- verify alignment from one picture.
    `dilate` grows/shrinks the polygon by that many feet first.
    """
    keep = oblique_keep(oriented, dsm, polygon, dilate, ray_step, buffer_px, step)
    return _draw_outline(oriented.image, keep, color, thickness, zoom, margin)


# =========================================================================== #
# Show / save helpers
# =========================================================================== #
def show(image, title=None, size=6):
    """Display an image inline (for notebooks)."""
    import matplotlib.pyplot as plt

    ar = image.shape[0] / image.shape[1]
    plt.figure(figsize=(size, size * ar))
    plt.imshow(image)
    plt.axis("off")
    if title:
        plt.title(title)
    plt.show()


def save(image, path):
    """Save an image to a PNG/JPG file."""
    from PIL import Image

    Image.fromarray(np.asarray(image, np.uint8)).save(path)


# --- helper: where does a ray overlap the DSM's ground footprint? -----------
def _ray_box_span(origins, directions, transform, shape):
    """Arc-length interval [enter, exit] where each ray is above the DSM's XY box."""
    h, w = shape
    xs, ys = [], []
    for c, r in [(0, 0), (w, 0), (0, h), (w, h)]:
        x, y = transform * (c, r)
        xs.append(x); ys.append(y)
    box = (min(xs), min(ys), max(xs), max(ys))
    lo = np.full(len(origins), -np.inf); hi = np.full(len(origins), np.inf)
    for axis, a, b in ((0, box[0], box[2]), (1, box[1], box[3])):
        d = directions[:, axis]; o = origins[:, axis]
        parallel = np.abs(d) < 1e-12
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (a - o) / d; t2 = (b - o) / d
        lo = np.where(parallel, lo, np.maximum(lo, np.minimum(t1, t2)))
        hi = np.where(parallel, hi, np.minimum(hi, np.maximum(t1, t2)))
        outside = parallel & ((o < a) | (o > b))
        lo = np.where(outside, np.nan, lo); hi = np.where(outside, np.nan, hi)
    return np.maximum(lo, 0.0), hi
