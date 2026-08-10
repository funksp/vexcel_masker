"""
api.py -- talk to the Vexcel Data Program API (v2) and return ready-to-use data.

Everything here takes a `token` (a short-lived login key) plus a location given
as `lon, lat` (x, y in degrees). The important functions are:

    get_token(username, password)     -> token string
    get_parcel(token, lon, lat)       -> the property boundary polygon
    get_structures(token, lon, lat)   -> the building footprint polygons
    get_dsm(token, lon, lat)          -> a DSM (height map) ready for ray-casting
    get_ortho(token, lon, lat)        -> a top-down ortho image (geo-referenced)
    get_oriented(token, lon, lat, "north") -> an oblique image + its solved camera

`best_collection(...)` finds a single dated flight that has the oblique, DSM and
ortho together, so all three layers come from the SAME DAY.

Auth note: the v2 API wants the token in the `Authorization: Bearer` header. (The
older `AuthToken` query parameter silently returns 403 even for a valid token.)
"""

from __future__ import annotations

import configparser
import io
import re
from dataclasses import dataclass

import numpy as np
import requests

from .camera import Camera, solve_camera
from .masking import DSM, Ortho

BASE_URL = "https://api.vexcelgroup.com/v2"


# =========================================================================== #
# Authentication
# =========================================================================== #
def get_token(username, password):
    """Log in and return a bearer token (valid ~24 h)."""
    r = requests.post(f"{BASE_URL}/auth/login",
                      json={"username": username, "password": password}, timeout=60)
    r.raise_for_status()
    return r.json()["token"]


def get_token_from_config(path="config.ini"):
    """Read [vexcel] username/password from an .ini file and log in."""
    cfg = configparser.ConfigParser()
    if not cfg.read(path):
        raise FileNotFoundError(f"config file not found: {path}")
    v = cfg["vexcel"]
    return get_token(v["username"], v["password"])


# =========================================================================== #
# Low-level request helpers
# =========================================================================== #
def _get(token, path, params):
    params = {k: v for k, v in params.items() if v is not None}
    r = requests.get(f"{BASE_URL}/{path}", params=params,
                     headers={"Authorization": f"Bearer {token}"}, timeout=120)
    if not r.ok:
        raise requests.HTTPError(f"{r.status_code} on {path}: {r.text[:200]}")
    return r


def _json(token, path, params):
    return _get(token, path, params).json()


def working_crs(lon, lat):
    """The UTM zone (in metres) for this location, e.g. 'EPSG:32618'."""
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def _wkt_point(lon, lat):
    return f"POINT({lon} {lat})"


# =========================================================================== #
# Collections (used to date-match the layers)
# =========================================================================== #
def _collections(token, kind, lon, lat, layer):
    j = _json(token, f"{kind}/collections",
              {"wkt": _wkt_point(lon, lat), "srid": "4326",
               "layer": layer, "metadata-format": "json"})
    return [f["properties"]["collection"] for f in j.get("features", [])
            if f.get("properties", {}).get("collection")]


def best_collection(token, lon, lat, layer="urban", want_ortho=True):
    """Most recent flight that has oblique + DSM (+ ortho) all together, or None."""
    common = set(_collections(token, "oriented", lon, lat, layer)) \
        & set(_collections(token, "dsm", lon, lat, layer))
    if want_ortho:
        common &= set(_collections(token, "ortho", lon, lat, layer))
    if not common:
        return None
    year = lambda name: int(re.search(r"(\d{4})", name).group(1)) if re.search(r"(\d{4})", name) else -1
    return max(common, key=year)


# =========================================================================== #
# Polygons: parcel + building footprints
# =========================================================================== #
def get_parcel(token, lon, lat):
    """Return the parcel polygon (in lon/lat) that contains the point."""
    from shapely.geometry import Point, shape

    j = _json(token, "property/extract",
              {"wkt": _wkt_point(lon, lat), "srid": "4326",
               "metadata-format": "json", "buffer-meter": 5})
    pt = Point(lon, lat)
    feats = j.get("features", [])
    if not feats:
        raise ValueError("no property found at this location")
    inside = [f for f in feats if shape(f["geometry"]).contains(pt)]
    chosen = inside[0] if inside else min(feats, key=lambda f: shape(f["geometry"]).distance(pt))
    return shape(chosen["geometry"])


def get_structures(token, lon, lat):
    """Return building footprint polygons (in lon/lat) on the parcel at the point."""
    from shapely.geometry import Point, shape
    from shapely import wkt as shp_wkt

    j = _json(token, "property/extract",
              {"wkt": _wkt_point(lon, lat), "srid": "4326",
               "metadata-format": "json", "buffer-meter": 5})
    pt = Point(lon, lat)
    feats = j.get("features", [])
    inside = [f for f in feats if shape(f["geometry"]).contains(pt)]
    chosen = inside[0] if inside else min(feats, key=lambda f: shape(f["geometry"]).distance(pt))
    polys = []
    for s in chosen["properties"].get("structures", []):
        w = s.get("footprint.wkt")
        if w:
            polys.append(shp_wkt.loads(w))
    return polys


# =========================================================================== #
# DSM and ortho
# =========================================================================== #
def get_dsm(token, lon, lat, size_m=300, resolution=0.3, collection=None, layer="urban"):
    """Download a DSM around the point and reproject it to the local UTM zone."""
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    r = _get(token, "dsm/extract",
             {"wkt": _wkt_point(lon, lat), "srid": "4326", "layer": layer,
              "bbox-dimensions": f"{int(size_m)},{int(size_m)}", "collection": collection})
    dst = working_crs(lon, lat)
    with MemoryFile(r.content) as mem, mem.open() as src:
        transform, w, h = calculate_default_transform(
            src.crs, dst, src.width, src.height, *src.bounds, resolution=resolution)
        data = np.full((h, w), np.nan, np.float32)
        reproject(rasterio.band(src, 1), data, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=transform, dst_crs=dst, resampling=Resampling.bilinear,
                  src_nodata=src.nodata, dst_nodata=np.nan)
    return DSM(data, transform, dst)


def get_ortho(token, lon, lat, size_m=150, pixels=1200, collection=None, layer="urban"):
    """Download a geo-referenced ortho image (GeoTIFF) around the point."""
    import rasterio
    from rasterio.io import MemoryFile

    r = _get(token, "ortho/extract",
             {"wkt": _wkt_point(lon, lat), "srid": "4326", "layer": layer,
              "bbox-dimensions": f"{int(size_m)},{int(size_m)}",
              "destination-dimensions": f"{int(pixels)},{int(pixels)}",
              "collection": collection, "image-format": "tiff", "bands": "rgb"})
    with MemoryFile(r.content) as mem, mem.open() as src:
        img = np.moveaxis(src.read()[:3], 0, -1).astype(np.uint8)
        return Ortho(img, src.transform, str(src.crs))


# =========================================================================== #
# Oblique image + solved camera
# =========================================================================== #
@dataclass
class Oriented:
    """An oblique image cropped to the area of interest, with its solved camera."""

    image: np.ndarray           # (H, W, 3) uint8
    camera: Camera
    direction: str
    meta: dict

    @property
    def collection(self):
        return self.meta.get("collection", "?")

    @property
    def date(self):
        return self.meta.get("capture-date", "")[:10]


_CAMERA_FIELDS = ("image-name,collection,capture-date,product-type,utm-zone,"
                  "camera-pos-x,camera-pos-y,camera-pos-z,ground-z,omega,phi,kappa")


def _world_to_pixel_oracle(token, image_name, lonlatz):
    """Ask Vexcel where 3-D ground points land in an image (for calibration)."""
    wkt = "MULTIPOINT Z (" + ",".join(f"({ln} {lt} {z})" for ln, lt, z in lonlatz) + ")"
    pts = _json(token, "oriented/transform-points",
                {"operation": "world-2-pixel", "image-name": image_name,
                 "wkt": wkt, "srid": "4326"})["points"]
    return np.array([[p["x"], p["y"]] for p in pts])


def get_oriented(token, lon, lat, direction, radius_m=120, downsample=1,
                 collection=None, layer="urban"):
    """Fetch the best oblique looking `direction` (north/south/east/west) at a point.

    Returns an `Oriented`: the image cropped to a `radius_m` box around the point
    plus the camera that projects world <-> pixel for that crop. The camera is
    solved by asking Vexcel where a grid of ground points lands (see camera.py).
    """
    from PIL import Image
    from pyproj import Transformer

    # 1. pick the image
    q = _json(token, "oriented/query",
              {"wkt": _wkt_point(lon, lat), "srid": "4326", "layer": layer,
               "product-type": f"oblique-{direction}", "collection": collection,
               "order-by": "image-center-distance-asc", "page-size": "1",
               "metadata-format": "json", "include": _CAMERA_FIELDS})
    feats = q.get("features", [])
    if not feats:
        raise ValueError(f"no '{direction}' oblique at this location")
    meta = feats[0]["properties"]

    # 2. download the whole native frame at the chosen pyramid level
    r = _get(token, "oriented/extract",
             {"image-name": meta["image-name"], "downsample": int(downsample),
              "bands": "rgb", "image-format": "jpeg"})
    frame = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))
    fh, fw = frame.shape[:2]
    full_w, full_h = fw * 2 ** downsample, fh * 2 ** downsample

    # 3. solve the camera from a grid of known ground<->pixel pairs near the point.
    #    We ask Vexcel where each 3-D point lands (it honours the Z we give). The
    #    points MUST span several heights -- a single flat plane of points does
    #    not pin down a perspective camera uniquely (it fits the plane but can be
    #    wildly wrong off it), so we stack the grid at a few elevations.
    crs = working_crs(lon, lat)
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    cx0, cy0 = to_utm.transform(lon, lat)
    z0 = float(meta.get("ground-z", 0.0))
    gx, gy = np.meshgrid(np.linspace(cx0 - 60, cx0 + 60, 5), np.linspace(cy0 - 60, cy0 + 60, 5))
    heights = z0 + np.array([0.0, 25.0, 50.0])          # three layers, not one plane
    X = np.tile(gx.ravel(), len(heights))
    Y = np.tile(gy.ravel(), len(heights))
    Z = np.repeat(heights, gx.size)
    lonlatz = [(*to_ll.transform(x, y), z) for x, y, z in zip(X, Y, Z)]
    pixels = _world_to_pixel_oracle(token, meta["image-name"], lonlatz)
    center = [meta["camera-pos-x"], meta["camera-pos-y"], meta["camera-pos-z"]]
    camera, _rms = solve_camera(center, meta["omega"], meta["phi"], meta["kappa"],
                                np.column_stack([X, Y, Z]), pixels, full_w, full_h)

    # 4. crop the frame to a box CENTRED on the point (robust: the point is always
    #    near the middle of the chosen image, so this can never be empty).
    scale = 1.0 / 2 ** downsample
    pu, pv = camera.world_to_pixel(cx0, cy0, z0)                 # the point, in pixels
    eu, ev = camera.world_to_pixel(cx0 + radius_m, cy0, z0)      # radius_m to the east
    px_per_m = np.hypot(eu - pu, ev - pv) / radius_m
    half = radius_m * px_per_m * scale
    if not np.isfinite(half) or half <= 0:
        half = 0.25 * min(fw, fh)                               # safety fallback
    cu, cv = pu * scale, pv * scale
    u0 = int(max(0, cu - half)); u1 = int(min(fw, cu + half))
    v0 = int(max(0, cv - half)); v1 = int(min(fh, cv + half))
    if u1 <= u0 or v1 <= v0:
        raise ValueError(f"the point is not visible in the '{direction}' oblique")
    crop = frame[v0:v1, u0:u1]
    crop_cam = camera.scaled(scale, (u0, v0), (u1 - u0, v1 - v0))
    return Oriented(crop, crop_cam, direction, meta)
