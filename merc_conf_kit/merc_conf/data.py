"""Snowflake -> pandas. Accepts a snowflake.connector connection or a Snowpark session. Do not edit."""
import pandas as pd

from . import config as C
from . import mapping as M

NUMERIC = ["merc", "sqft", "pcs", "prefill_merc", "prefill_low", "prefill_high", "prefill_sqft",
           "final_merc", "final_low", "final_high", "final_sqft"]


def run_sql(conn, sql):
    if hasattr(conn, "sql") and not hasattr(conn, "cursor"):       # Snowpark Session
        df = conn.sql(sql).to_pandas()
    else:                                                            # snowflake.connector
        cur = conn.cursor()
        try:
            cur.execute(sql)
            df = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
        finally:
            cur.close()
    df.columns = [c.lower() for c in df.columns]
    for c in NUMERIC:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _fill(template, start, end):
    return template.format(start=str(start)[:10], end=str(end)[:10], silver=M.SILVER_PROPERTY)


def load_book(conn, start, end):
    """Bound policies with start <= date < end ('YYYY-MM-DD'). Columns: see mapping.BOOK_SQL."""
    return run_sql(conn, _fill(M.BOOK_SQL, start, end))


def load_quotes(conn, start, end):
    """Quotes with start <= date < end. Columns: see mapping.QUOTES_SQL."""
    return run_sql(conn, _fill(M.QUOTES_SQL, start, end))


def cells_for_house(conn, house_id):
    """{"state":.., "h3_r4":.., ..} for one HOUSE_ID from SILVER_PROPERTY."""
    hid = str(house_id).replace("'", "")
    df = run_sql(conn, f"SELECT STATE, H3_R4, H3_R5, H3_R6, H3_R7 FROM {M.SILVER_PROPERTY} "
                       f"WHERE HOUSE_ID = '{hid}' LIMIT 1")
    return {lvl: df.iloc[0][lvl] for lvl in C.LEVELS} if len(df) else {}
