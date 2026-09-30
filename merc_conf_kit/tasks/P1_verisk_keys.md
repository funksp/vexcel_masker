# P1 · Verisk field names
Goal: `verisk.to_estimate()` reads the dict returned by `client.rebuild_cost_custom(...)`.
Read: `merc_conf/mapping.py` (P1 section only), `fixtures/verisk_summary.json`
Edit: `merc_conf/mapping.py` (P1 section only)

## Human first (in the Verisk notebook)
```python
import json
base = client.rebuild_cost_custom(street=..., city=..., state=..., zipcode=..., show=True)
over = client.rebuild_cost_custom(street=..., city=..., state=..., zipcode=...,
    valuation_id=base["valuation_id"],
    characteristics=[characteristic("GENERALINFO", totalfinishedsqft=1500)], show=True)
print(json.dumps(base, default=str)); print(json.dumps(over, default=str))
```
Copy `fixtures/verisk_summary.TEMPLATE.json` to `fixtures/verisk_summary.json`.
Paste each printed dict into "summary". Fill "_expected" from the `show=True` printout:
merc = Replacement cost, low/high = Range, iscore = iScore, sqft = Replacement cost ÷ Cost per sq ft.
Replace street/city text in the pasted dicts with "REDACTED".

## Agent steps
1. In the fixture, find the keys for: range low, range high, cost per sq ft, iScore.
2. In `mapping.py`, replace `TODO_low`, `TODO_high`, `TODO_ppsf`, `TODO_iscore` with those keys.
   If a value is nested, index into it (e.g. `s["range"]["low"]`). Keep the `num(...)` wrapper.
3. Run `pytest tests/test_mapping.py -k p1`.

Done when the test passes. Append to PROGRESS.md.
