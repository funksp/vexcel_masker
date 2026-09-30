import math

import pandas as pd

from merc_conf import data, shadow

REF = pd.DataFrame([(lvl, 1, cell, n, med, mad) for lvl, cell, n, med, mad in [
    ("state", "TX", 48_000, math.log(168), 0.110), ("h3_r4", "a", 2_400, math.log(176), 0.090),
    ("h3_r5", "b", 310, math.log(179), 0.080), ("h3_r6", "c", 42, math.log(184), 0.070),
    ("h3_r7", "d", 9, math.log(190), 0.050)]], columns=["level", "size_band", "cell", "n", "median", "mad"])
CELLS = {"state": "TX", "h3_r4": "a", "h3_r5": "b", "h3_r6": "c", "h3_r7": "d"}
COLS = ["quote_id", "prefill_merc", "prefill_low", "prefill_high", "prefill_sqft",
        "final_merc", "final_low", "final_high", "final_sqft", "pcs"]
QUOTES = pd.DataFrame([
    (1, 335_000, 306_000, 367_000, 1_950, 372_000, 341_000, 405_000, 2_150, 3),
    (2, 380_000, 352_000, 410_000, 2_050, 380_000, 352_000, 410_000, 2_050, 5),
    (3, 400_000, 364_000, 440_000, 2_200, 300_000, 272_000, 331_000, 1_950, 2),
    (4, None, None, None, None, None, None, None, None, 3)], columns=COLS).assign(**CELLS)


def test_score_frame_matches_doc():
    res = shadow.score_frame(QUOTES, REF)
    assert list(res["tier"]) == ["Medium", "High", "Low", "Error"]
    assert [round(c, 3) for c in res["confidence"][:3]] == [0.848, 0.976, 0.479]
    assert "3 errors" not in shadow.summary(res) and "1 errors" in shadow.summary(res)


class FakeCursor:
    description = [("MERC",), ("SQFT",)]
    def execute(self, sql): self.sql = sql
    def fetchall(self): return [("372000", 2150)]
    def close(self): pass


class FakeConn:
    def cursor(self): return FakeCursor()


def test_run_sql_lowercases_and_casts():
    df = data.run_sql(FakeConn(), "select 1")
    assert list(df.columns) == ["merc", "sqft"] and df["merc"][0] == 372_000.0
