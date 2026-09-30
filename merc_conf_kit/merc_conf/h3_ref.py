"""Neighborhood $/sqft reference from the book. Pure pandas, fully tested. Do not edit."""
import math

import numpy as np
import pandas as pd

from . import config as C
from .schema import Neighborhood


def size_band(sqft):
    return int(np.searchsorted(C.SIZE_BANDS, sqft, side="right"))


def build_reference(book):
    """book columns: merc, sqft, state, h3_r4..h3_r7 (one row per property).
    Returns one row per (level, size_band, cell): n, median, mad of log $/sqft."""
    df = book[(book["sqft"] >= C.MIN_SQFT) & (book["merc"] > 0)].copy()
    df["y"] = np.log(df["merc"] / df["sqft"])
    df["size_band"] = np.searchsorted(C.SIZE_BANDS, df["sqft"].to_numpy(), side="right")
    parts = []
    for lvl in C.LEVELS:
        keys = [df["size_band"], df[lvl]]
        g = df.groupby(keys)["y"]
        dev = (df["y"] - g.transform("median")).abs()
        s = pd.DataFrame({"n": g.size(), "median": g.median(), "mad": dev.groupby(keys).median()})
        s.index.names = ["size_band", "cell"]
        s = s.reset_index()
        s["level"], s["cell"] = lvl, s["cell"].astype(str)
        parts.append(s)
    return pd.concat(parts, ignore_index=True)[["level", "size_band", "cell", "n", "median", "mad"]]


def index(ref):
    """Fast lookup: {(level, size_band, cell): (n, median, mad)}."""
    return {(r.level, int(r.size_band), str(r.cell)): (int(r.n), float(r.median), float(r.mad))
            for r in ref.itertuples(index=False)}


def blend(found):
    """found: [(level, (n, median, mad)), ...] coarse to fine -> Neighborhood."""
    center, mad0 = found[0][1][1], found[0][1][2]
    log_mad = math.log(max(mad0, C.MAD_FLOOR))
    for _, (n, med, mad) in found[1:]:
        w = n / (n + C.K_CRED)
        ws = w if n >= 3 else 0.0
        center = w * med + (1 - w) * center
        log_mad = ws * math.log(max(mad, C.MAD_FLOOR)) + (1 - ws) * log_mad
    n_r5 = next((v[0] for lvl, v in found if lvl == "h3_r5"), 0)
    return Neighborhood(center, 1.4826 * math.exp(log_mad), n_r5)


def neighborhood(idx, sqft, cells):
    """cells: {"state": .., "h3_r4": .., ..., "h3_r7": ..}. Returns Neighborhood or None."""
    band = size_band(sqft)
    found = [(lvl, idx.get((lvl, band, str(cells.get(lvl))))) for lvl in C.LEVELS]
    found = [(lvl, v) for lvl, v in found if v is not None]
    return blend(found) if found else None
