import math

import numpy as np
import pandas as pd

from merc_conf import h3_ref

DOC_CELLS = [("state", (48_000, math.log(168), 0.110)), ("h3_r4", (2_400, math.log(176), 0.090)),
             ("h3_r5", (310, math.log(179), 0.080)), ("h3_r6", (42, math.log(184), 0.070)),
             ("h3_r7", (9, math.log(190), 0.050))]


def test_blend_matches_doc():
    nb = h3_ref.blend(DOC_CELLS)
    assert abs(math.exp(nb.center) - 184.11) < 0.01 and abs(nb.spread - 0.0987) < 1e-3 and nb.n_r5 == 310


def test_size_bands():
    assert [h3_ref.size_band(s) for s in (1799, 1800, 2499, 2500, 3500)] == [0, 1, 1, 2, 3]


def synthetic_book(n=5000, seed=1):
    rng = np.random.default_rng(seed)
    r7 = rng.integers(0, 40, n)
    sqft = rng.lognormal(np.log(2000), 0.3, n)
    return pd.DataFrame({"merc": sqft * 180 * np.exp(rng.normal(0, 0.1, n)), "sqft": sqft, "state": "TX",
                         "h3_r4": "a", "h3_r5": [f"b{i % 4}" for i in r7], "h3_r6": [f"c{i % 10}" for i in r7],
                         "h3_r7": [f"d{i}" for i in r7]})


def test_build_and_lookup():
    ref = h3_ref.build_reference(synthetic_book())
    assert set(ref.columns) == {"level", "size_band", "cell", "n", "median", "mad"}
    nb = h3_ref.neighborhood(h3_ref.index(ref), 2100, {"state": "TX", "h3_r4": "a", "h3_r5": "b1",
                                                       "h3_r6": "c3", "h3_r7": "d13"})
    assert 150 < math.exp(nb.center) < 210 and 0.05 < nb.spread < 0.2 and nb.n_r5 > 30
    assert h3_ref.neighborhood(h3_ref.index(ref), 2100, {"state": "ZZ"}) is None
