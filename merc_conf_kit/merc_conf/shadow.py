"""Score a quotes DataFrame (columns: see mapping.QUOTES_SQL). Changes nothing. Do not edit."""
import pandas as pd

from . import config as C
from . import core, h3_ref
from .schema import Estimate

WATERFALL_COLS = ["c_range", "c_pcs", "c_nbhd", "c_final"]


def _val(r, k):
    v = r.get(k)
    return None if v is None or pd.isna(v) else float(v)


def _estimate(r, prefix):
    merc, sqft = _val(r, f"{prefix}_merc"), _val(r, f"{prefix}_sqft")
    if merc is None or sqft is None:
        return None
    return Estimate(merc, _val(r, f"{prefix}_low"), _val(r, f"{prefix}_high"), sqft)


def score_frame(quotes, ref):
    idx = h3_ref.index(ref)
    rows = []
    for r in quotes.to_dict("records"):
        out = {"quote_id": r.get("quote_id")}
        try:
            fin = _estimate(r, "final")
            if fin is None:
                raise ValueError("no final MERC or sqft")
            nb = h3_ref.neighborhood(idx, fin.sqft, {lvl: r.get(lvl) for lvl in C.LEVELS})
            res = core.score(_estimate(r, "prefill"), fin, _val(r, "pcs"), nb)
            out.update(confidence=res.confidence, tier=res.tier, main_driver=res.main_driver,
                       reason=res.reason, flags="; ".join(res.flags), z=res.z)
            out.update(dict(zip(WATERFALL_COLS, [v for _, v in res.waterfall])))
        except Exception as e:                       # one bad row never stops the batch
            out.update(tier="Error", reason=str(e))
        rows.append(out)
    return pd.DataFrame(rows)


def summary(results):
    ok = results[results["tier"] != "Error"]
    lines = [f"{len(results)} quotes, {len(results) - len(ok)} errors"]
    for t in ("High", "Medium", "Low"):
        k = int((ok["tier"] == t).sum())
        lines.append(f"  {t:<7}{k:>8}  {k / max(len(ok), 1):6.1%}")
    lines.append("Main drivers:")
    lines += [f"  {d}: {c}" for d, c in ok["main_driver"].value_counts().items()] if len(ok) else []
    return "\n".join(lines)
