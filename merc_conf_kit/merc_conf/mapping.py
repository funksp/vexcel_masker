"""Environment-specific names. The ONLY package file agents edit (cards P1-P3)."""

# ============ P1: Verisk summary dict from client.rebuild_cost_custom(...) ============
# A value may be a string like "$612,049.00"; num() cleans it.
def num(x):
    return float(str(x).replace("$", "").replace(",", "")) if x not in (None, "") else None

def get_cost(s):          return num(s["cost"])                 # confirmed from notebook
def get_valuation_id(s):  return s["valuation_id"]              # confirmed from notebook
def get_range(s):         return num(s["TODO_low"]), num(s["TODO_high"])   # TODO P1
def get_cost_per_sqft(s): return num(s["TODO_ppsf"])            # TODO P1
def get_iscore(s):        return num(s["TODO_iscore"])          # TODO P1

def get_pcs(prefill):
    """Property Confidence Score (1-5). Human decision: iScore of the PREFILL valuation."""
    return prefill.iscore


# ============ P2: book of bound policies -> neighborhood reference ============
SILVER_PROPERTY = "PPNCEZ937.EZ937.SILVER_PROPERTY"

# Must return exactly these aliases: merc, sqft, state, h3_r4, h3_r5, h3_r6, h3_r7
# {start} {end} {silver} are filled in by data.py. One row per HOUSE_ID (latest).
BOOK_SQL = """
SELECT b.TODO_MERC_COL AS merc, b.TODO_SQFT_COL AS sqft,
       p.STATE AS state, p.H3_R4 AS h3_r4, p.H3_R5 AS h3_r5, p.H3_R6 AS h3_r6, p.H3_R7 AS h3_r7
FROM TODO_BOOK_TABLE b
JOIN {silver} p ON p.HOUSE_ID = b.HOUSE_ID
WHERE b.TODO_DATE_COL >= '{start}' AND b.TODO_DATE_COL < '{end}'
  AND TODO_BOUND_FILTER
QUALIFY ROW_NUMBER() OVER (PARTITION BY b.HOUSE_ID ORDER BY b.TODO_DATE_COL DESC) = 1
"""


# ============ P3: quotes to score in shadow mode ============
# Must return exactly these aliases (use NULL AS <alias> if a value is not stored):
# quote_id, quote_date, prefill_merc, prefill_low, prefill_high, prefill_sqft,
# final_merc, final_low, final_high, final_sqft, pcs, state, h3_r4, h3_r5, h3_r6, h3_r7
QUOTES_SQL = """
SELECT TODO_SELECT_LIST
FROM TODO_QUOTES_TABLE q
JOIN {silver} p ON p.HOUSE_ID = q.HOUSE_ID
WHERE q.TODO_QUOTE_DATE_COL >= '{start}' AND q.TODO_QUOTE_DATE_COL < '{end}'
"""
