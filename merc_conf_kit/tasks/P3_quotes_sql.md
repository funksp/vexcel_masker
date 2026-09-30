# P3 · Quotes query (what shadow mode scores)
Goal: `QUOTES_SQL` returns one row per quote with the 16 aliases listed in mapping.py.
Read: `merc_conf/mapping.py` (P3 section only)
Edit: `merc_conf/mapping.py` (P3 section only)

## Human gives the agent (paste into chat)
- Quotes table name, and its columns for: quote id, quote date, HOUSE_ID,
  prefill MERC / range low / range high / sq ft, final MERC / range low / range high / sq ft,
  iScore of the PREFILL valuation.
- Which of these are NOT stored.

## Agent steps
1. Replace `TODO_SELECT_LIST` with one line per alias, in this order:
   `q.<col> AS quote_id, q.<col> AS quote_date, q.<col> AS prefill_merc, ... , q.<col> AS pcs,`
   then `p.STATE AS state, p.H3_R4 AS h3_r4, p.H3_R5 AS h3_r5, p.H3_R6 AS h3_r6, p.H3_R7 AS h3_r7`.
2. Not stored → `NULL AS <alias>`. Sq ft not stored but cost per sq ft is → `q.<merc> / q.<ppsf> AS final_sqft`.
3. Replace `TODO_QUOTES_TABLE` and `TODO_QUOTE_DATE_COL`. Keep `{silver}`, `{start}`, `{end}`.
4. Same H3 integer rule as P2.
5. Run `pytest tests/test_mapping.py -k p3`.

Done when the test passes. Append to PROGRESS.md.
