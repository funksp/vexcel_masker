"""MERC confidence math. Pure functions, fully tested. Do not edit."""
import math

import numpy as np

from . import config as C
from .schema import Estimate, Neighborhood, Result

STEPS = [
    ("Final MERC range", dict(use_pcs=False, use_nbhd=False, use_prefill=False)),
    ("Property Confidence Score", dict(use_nbhd=False, use_prefill=False)),
    ("Neighborhood estimate", dict(use_prefill=False)),
    ("Prefill vs. final", dict()),
]


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def sigma_pcs(pcs):
    """Leftover data risk for a Property Confidence Score (decimals interpolate)."""
    return float(np.interp(pcs, C.PCS_POINTS, C.PCS_SIGMA))


def range_spread(e):
    """A Verisk range as a log-scale standard deviation (None if no range)."""
    if e is None or not e.low or not e.high:
        return None
    return math.log(e.high / e.low) / (2 * C.RANGE_Z)


def in_tolerance(offset, sd):
    """Chance the quote is within tolerance when the truth is centered `offset` (log) away."""
    return _phi((C.TOL_UNDER - offset) / sd) - _phi((-C.TOL_OVER - offset) / sd)


def _version(e, quote_merc, s_engine, pcs, nb, use_pcs, use_nbhd):
    """Confidence for one version of the house (member right = final, member wrong = prefill)."""
    s = math.hypot(s_engine, sigma_pcs(pcs) if use_pcs else 0.0)
    offset = math.log(e.merc / quote_merc)
    if use_nbhd and nb is not None:
        pull = s * s / (s * s + nb.spread ** 2)
        offset += pull * math.log(math.exp(nb.center) * e.sqft / e.merc)
    return in_tolerance(offset, max(s, 1e-9))


def confidence(prefill, final, pcs, nb, use_pcs=True, use_nbhd=True, use_prefill=True):
    s_final = range_spread(final) or range_spread(prefill)
    right = _version(final, final.merc, s_final, pcs, nb, use_pcs, use_nbhd)
    if not use_prefill or prefill is None or math.isclose(prefill.merc, final.merc):
        return right
    s_pre = range_spread(prefill) or s_final
    wrong = _version(prefill, final.merc, s_pre, pcs, nb, use_pcs, use_nbhd)
    return (1 - C.P_MEMBER_WRONG) * right + C.P_MEMBER_WRONG * wrong


def score(prefill, final, pcs, nb):
    """prefill: Estimate or None; final: Estimate; pcs: 1-5 or None; nb: Neighborhood or None."""
    if range_spread(final) is None and range_spread(prefill) is None:
        return Result(0.0, "Low", "Final MERC range", "no Verisk range", ["no Verisk range"])
    flags = []
    if range_spread(final) is None:
        flags.append("final range missing; used prefill range")
    if pcs is None:
        flags.append("PCS missing; treated as 1")
        pcs = 1
    if prefill is None:
        flags.append("no prefill MERC to compare")
    if nb is None:
        flags.append("no neighborhood reference")
    wf = [(label, confidence(prefill, final, pcs, nb, **kw)) for label, kw in STEPS]
    c = wf[-1][1]
    tier = "High" if c >= C.HIGH_CUT else "Medium" if c >= C.LOW_CUT else "Low"
    z = None
    if nb is not None:
        z = (math.log(final.merc / final.sqft) - nb.center) / nb.spread
        if nb.n_r5 < C.MIN_NEARBY:
            flags.append(f"few comparable homes nearby ({nb.n_r5} in r5)")
        if abs(z) > C.EXTREME_Z:
            flags.append("far outside the neighborhood's $/sqft")
    if flags and tier == "High":
        tier = "Medium"
    before = [1.0] + [v for _, v in wf[:-1]]
    drops = {label: b - v for (label, v), b in zip(wf, before)}
    driver = max(drops, key=drops.get)
    return Result(c, tier, driver, _reason(driver, prefill, final, pcs, nb), flags, z, wf)


def _reason(driver, prefill, final, pcs, nb):
    if driver == "Final MERC range":
        s = range_spread(final) or range_spread(prefill)
        return f"Verisk's range is about ±{s * C.RANGE_Z:.0%}"
    if driver == "Property Confidence Score":
        return f"Verisk's data on this home is rated {pcs:g} of 5"
    if driver == "Neighborhood estimate":
        ppsf, typ = final.merc / final.sqft, math.exp(nb.center)
        return f"${ppsf:,.0f}/sq ft vs. ${typ:,.0f} typical nearby ({ppsf / typ - 1:+.0%})"
    shift = final.merc / prefill.merc - 1
    outside = bool(prefill.low and prefill.high) and not prefill.low <= final.merc <= prefill.high
    return f"member changes moved MERC {shift:+.0%}" + (", outside Verisk's prefill range" if outside else "")
