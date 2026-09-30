"""Verisk summary -> Estimate. Field names live in mapping.py. Do not edit."""
from . import mapping as M
from .schema import Estimate


def to_estimate(summary):
    merc = M.get_cost(summary)
    low, high = M.get_range(summary)
    return Estimate(merc=merc, low=low, high=high, sqft=merc / M.get_cost_per_sqft(summary),
                    iscore=M.get_iscore(summary), valuation_id=M.get_valuation_id(summary))


def value_home(client, street, city, state, zipcode, valuation_id=None, overrides=None):
    """One rebuild_cost_custom call. No overrides = prefill; overrides = final.
    Use this same call for both so prefill and final are comparable."""
    kw = dict(street=street, city=city, state=state, zipcode=zipcode)
    if valuation_id:
        kw["valuation_id"] = valuation_id
    if overrides:
        kw["characteristics"] = overrides
    return to_estimate(client.rebuild_cost_custom(**kw))
