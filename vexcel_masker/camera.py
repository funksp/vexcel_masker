"""
camera.py -- the geometry of an aerial camera.

An oblique aerial photo is a *perspective* picture of a 3-D scene. To mask it we
need to know, for any pixel, which ray of light in the real world produced it.
That is what a camera model gives us.

Two operations matter:

  * world_to_pixel(X, Y, Z) : where does a real-world point land in the image?
  * pixel_to_ray(u, v)      : what world-space ray does this pixel look along?

We use the standard "pinhole" camera. In OUR convention the camera looks down
its +Z axis, with +X to the right and +Y downward in the image. A world point P
is turned into a pixel like this:

    camera_coords = R_worldToCamera @ (P - camera_center)     # rotate + translate
    x_norm = camera_coords.x / camera_coords.z                # perspective divide
    y_norm = camera_coords.y / camera_coords.z
    u = cx + focal * x_norm                                   # scale to pixels
    v = cy + focal * y_norm

`focal` is in pixels, and (cx, cy) is the image centre ("principal point").

The only tricky part with real Vexcel data is the ROTATION. Vexcel gives three
angles (omega, phi, kappa), but different camera models order and sign those
angles differently. Rather than guess, `solve_camera` tries every standard
convention against a few known point<->pixel pairs and keeps the one that fits.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np


# --- basic rotation matrices about each axis (angle in radians) -------------
def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


_ROT = {"x": rot_x, "y": rot_y, "z": rot_z}


@dataclass
class Camera:
    """A solved pinhole camera in a projected CRS (metres)."""

    center: np.ndarray          # (X0, Y0, Z0) perspective centre, world metres
    rotation: np.ndarray        # 3x3 world-to-camera rotation
    focal: float                # focal length in PIXELS
    cx: float                   # principal point x (pixels)
    cy: float                   # principal point y (pixels)
    width: int                  # image width  (pixels)
    height: int                 # image height (pixels)

    def world_to_pixel(self, X, Y, Z):
        """Project world point(s) to pixel (u, v). Points behind the camera -> NaN."""
        P = np.stack(np.broadcast_arrays(X, Y, Z), axis=-1).astype(float)
        cam = (P - self.center) @ self.rotation.T   # into camera frame
        z = cam[..., 2]
        z = np.where(z > 1e-6, z, np.nan)           # behind camera -> invalid
        u = self.cx + self.focal * cam[..., 0] / z
        v = self.cy + self.focal * cam[..., 1] / z
        return u, v

    def pixel_to_ray(self, u, v):
        """Return (origin, direction) of the world-space ray through pixel (u, v)."""
        u = np.asarray(u, float)
        v = np.asarray(v, float)
        # direction in the camera frame, then rotate out into the world
        dir_cam = np.stack([(u - self.cx) / self.focal,
                            (v - self.cy) / self.focal,
                            np.ones_like(u)], axis=-1)
        dir_world = dir_cam @ self.rotation          # camera -> world
        dir_world /= np.linalg.norm(dir_world, axis=-1, keepdims=True)
        origin = np.broadcast_to(self.center, dir_world.shape)
        return origin, dir_world

    def scaled(self, scale, crop_origin=(0.0, 0.0), size=None):
        """A copy of this camera for a downsampled and/or cropped version of the image.

        `scale` = 1 / 2**downsample. `crop_origin` = (u0, v0) removed from the
        top-left. Pixel coordinates simply scale and shift, so the geometry stays
        exact.
        """
        u0, v0 = crop_origin
        w, h = size if size else (round(self.width * scale), round(self.height * scale))
        return Camera(self.center, self.rotation,
                      self.focal * scale,
                      self.cx * scale - u0, self.cy * scale - v0,
                      int(w), int(h))


# every "standard" way three angles can be turned into a rotation -----------
def _rotation_from_convention(omega, phi, kappa, order, signs, transpose, flip):
    a = {"x": omega * signs[0], "y": phi * signs[1], "z": kappa * signs[2]}
    R = _ROT[order[0]](a[order[0]]) @ _ROT[order[1]](a[order[1]]) @ _ROT[order[2]](a[order[2]])
    if transpose:
        R = R.T
    return R @ np.diag(flip)


_ALL_CONVENTIONS = [
    (order, signs, transpose, flip)
    for order in itertools.permutations("xyz")
    for signs in itertools.product((1, -1), repeat=3)
    for transpose in (False, True)
    for flip in itertools.product((1, -1), repeat=3)
]


def solve_camera(center, omega, phi, kappa, world_points, pixels, width, height):
    """Find the Camera that maps `world_points` (N x 3) to `pixels` (N x 2).

    We know the perspective centre and the three angles, but not the exact angle
    convention this particular Vexcel camera uses. So we try them all and keep
    whichever reproduces the known pixels best. For a correct convention the fit
    is essentially perfect (sub-pixel), which also validates the whole geometry.
    """
    center = np.asarray(center, float)
    world_points = np.asarray(world_points, float)
    pixels = np.asarray(pixels, float)
    rel = world_points - center

    best = None  # (rms, rotation, focal, cx, cy)
    for order, signs, transpose, flip in _ALL_CONVENTIONS:
        R = _rotation_from_convention(omega, phi, kappa, order, signs, transpose, flip)
        cam = rel @ R.T
        z = cam[:, 2]
        if np.any(z <= 1e-6):          # some points behind camera -> wrong convention
            continue
        xn, yn = cam[:, 0] / z, cam[:, 1] / z
        # fit  u = cx + f*xn  and  v = cy + f*yn  (least squares, per axis)
        fx, cx = np.polyfit(xn, pixels[:, 0], 1)
        fy, cy = np.polyfit(yn, pixels[:, 1], 1)
        pred_u, pred_v = fx * xn + cx, fy * yn + cy
        rms = np.sqrt(np.mean((pred_u - pixels[:, 0]) ** 2 + (pred_v - pixels[:, 1]) ** 2))
        if best is None or rms < best[0]:
            # The two axes may need a sign flip so a single positive focal works.
            # This flips only the image x/y axes (LEFT-multiply) -- folding it on
            # the right would also flip depth and put points behind the camera.
            R_final = np.diag([np.sign(fx), np.sign(fy), 1.0]) @ R
            best = (rms, R_final, 0.5 * (abs(fx) + abs(fy)), cx, cy)

    if best is None:
        raise RuntimeError("no camera convention fit the points (all behind camera?)")
    rms, rotation, focal, cx, cy = best
    return Camera(center, rotation, focal, cx, cy, int(width), int(height)), rms
