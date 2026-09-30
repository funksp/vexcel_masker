"""Phase gates. These FAIL until the matching task card is done (that is expected)."""
import inspect
import json
import pathlib

import pytest

from merc_conf import mapping as M
from merc_conf import verisk

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "verisk_summary.json"
QUOTE_COLS = ["quote_id", "quote_date", "prefill_merc", "prefill_low", "prefill_high", "prefill_sqft",
              "final_merc", "final_low", "final_high", "final_sqft", "pcs",
              "state", "h3_r4", "h3_r5", "h3_r6", "h3_r7"]


def test_p1_verisk_keys():
    getters = [M.get_range, M.get_cost_per_sqft, M.get_iscore]
    assert not any("TODO_" in inspect.getsource(g) for g in getters), "P1: replace TODO_ keys in mapping.py"
    if not FIXTURE.exists():
        pytest.fail("P1: create fixtures/verisk_summary.json (see tasks/P1_verisk_keys.md)")
    for case in json.loads(FIXTURE.read_text()):
        e, x = verisk.to_estimate(case["summary"]), case["_expected"]
        assert abs(e.merc - x["merc"]) < 1 and abs(e.low - x["low"]) < 1 and abs(e.high - x["high"]) < 1
        assert abs(e.sqft - x["sqft"]) < 1.5 and abs(e.iscore - x["iscore"]) < 0.01


def test_p2_book_sql():
    assert "TODO_" not in M.BOOK_SQL, "P2: replace TODO_ names in BOOK_SQL"
    for alias in ["merc", "sqft", "state", "h3_r4", "h3_r5", "h3_r6", "h3_r7"]:
        assert f"AS {alias}" in M.BOOK_SQL
    M.BOOK_SQL.format(start="2025-01-01", end="2026-01-01", silver=M.SILVER_PROPERTY)


def test_p3_quotes_sql():
    assert "TODO_" not in M.QUOTES_SQL, "P3: replace TODO_ names in QUOTES_SQL"
    for alias in QUOTE_COLS:
        assert f"AS {alias}" in M.QUOTES_SQL, f"missing alias: AS {alias}"
    M.QUOTES_SQL.format(start="2025-01-01", end="2026-01-01", silver=M.SILVER_PROPERTY)
