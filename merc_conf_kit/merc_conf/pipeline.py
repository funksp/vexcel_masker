"""Score one address live (like the Verisk notebook examples). Do not edit."""
from . import core, h3_ref, verisk
from . import mapping as M


def score_live(client, street, city, state, zipcode, cells, idx, overrides=None):
    """cells: data.cells_for_house(...); idx: h3_ref.index(ref);
    overrides: [characteristic(...), ...] = the member's changes. Returns (Result, prefill, final)."""
    pre = verisk.value_home(client, street, city, state, zipcode)
    fin = (verisk.value_home(client, street, city, state, zipcode, pre.valuation_id, overrides)
           if overrides else pre)
    nb = h3_ref.neighborhood(idx, fin.sqft, cells)
    return core.score(pre, fin, M.get_pcs(pre), nb), pre, fin
