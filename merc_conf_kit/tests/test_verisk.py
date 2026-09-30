"""Adapter logic, independent of mapping.py key names (they are patched here)."""
import pytest

from merc_conf import mapping as M
from merc_conf import verisk


@pytest.fixture(autouse=True)
def known_keys(monkeypatch):
    monkeypatch.setattr(M, "get_range", lambda s: (M.num(s["lo"]), M.num(s["hi"])))
    monkeypatch.setattr(M, "get_cost_per_sqft", lambda s: M.num(s["ppsf"]))
    monkeypatch.setattr(M, "get_iscore", lambda s: M.num(s["isc"]))


class FakeClient:
    def __init__(self):
        self.calls = []

    def rebuild_cost_custom(self, **kw):
        self.calls.append(kw)
        cost = 764_991.28 if "characteristics" in kw else 627_292.90
        return {"cost": cost, "lo": "$612,585.00", "hi": 642_000, "ppsf": cost / (1500 if kw.get("characteristics") else 1061),
                "isc": 4.0, "valuation_id": "V1"}


def test_prefill_then_final():
    c = FakeClient()
    pre = verisk.value_home(c, "s", "c", "TX", "78210")
    fin = verisk.value_home(c, "s", "c", "TX", "78210", pre.valuation_id, ["override"])
    assert round(pre.sqft) == 1061 and pre.low == 612_585 and pre.iscore == 4.0
    assert round(fin.sqft) == 1500 and c.calls[1]["valuation_id"] == "V1" and c.calls[1]["characteristics"] == ["override"]
    assert "valuation_id" not in c.calls[0]
