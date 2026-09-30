# P2 · Book query (neighborhood reference)
Goal: `BOOK_SQL` returns one row per property: merc, sqft, state, h3_r4..h3_r7.
Read: `merc_conf/mapping.py` (P2 section only)
Edit: `merc_conf/mapping.py` (P2 section only)

## Human gives the agent (paste into chat)
- Table with final MERC + sq ft per policy, and its column names for:
  MERC, sq ft, HOUSE_ID, date (bind/effective), bound filter (e.g. `b.STATUS = 'BOUND'`).
- Whether H3_R4..H3_R7 in SILVER_PROPERTY are strings or integers.

## Agent steps
1. Replace every `TODO_...` in `BOOK_SQL` with the names given. Keep every `AS <alias>` exactly.
2. Keep `{silver}`, `{start}`, `{end}` placeholders as they are.
3. If H3 columns are integers, wrap each: `H3_INT_TO_STRING(p.H3_R7) AS h3_r7`.
4. Run `pytest tests/test_mapping.py -k p2`.

## Human check (notebook)
```python
from merc_conf import data
b = data.load_book(conn, "2025-01-01", "2026-07-01"); print(b.shape); print(b.head())
```
Done when the test passes and `b` has rows with no null merc/sqft. Append to PROGRESS.md.
