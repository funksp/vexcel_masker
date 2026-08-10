"""
vexcel_masker -- pull Vexcel imagery and mask it to a parcel or building.

Typical use (see demo.ipynb):

    import vexcel_masker as vm

    token = vm.get_token_from_config("config.ini")
    lon, lat = -76.876653, 38.757577

    parcel     = vm.get_parcel(token, lon, lat)
    structures = vm.get_structures(token, lon, lat)

    coll  = vm.best_collection(token, lon, lat)          # same-day flight
    dsm   = vm.get_dsm(token, lon, lat, collection=coll)
    ortho = vm.get_ortho(token, lon, lat, collection=coll)
    north = vm.get_oriented(token, lon, lat, "north", collection=coll)

    vm.show(vm.mask_oblique(north, dsm, parcel,     fill="magenta"))
    vm.show(vm.mask_ortho(ortho, structures, fill="average"))
"""

from .api import (
    best_collection,
    get_dsm,
    get_oriented,
    get_ortho,
    get_parcel,
    get_structures,
    get_token,
    get_token_from_config,
    working_crs,
)
from .camera import Camera, solve_camera
from .masking import (
    DSM,
    Ortho,
    mask_oblique,
    mask_ortho,
    outline_oblique,
    outline_ortho,
    resolve_fill,
    save,
    show,
)

__all__ = [
    "get_token", "get_token_from_config",
    "get_parcel", "get_structures",
    "best_collection", "get_dsm", "get_ortho", "get_oriented",
    "mask_oblique", "mask_ortho", "outline_oblique", "outline_ortho",
    "resolve_fill", "show", "save",
    "Camera", "solve_camera", "DSM", "Ortho", "working_crs",
]
