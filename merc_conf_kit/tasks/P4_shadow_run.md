# P4 · First shadow run
Goal: `shadow_run.py` runs top to bottom and writes `shadow_results.csv`.
Read: `shadow_run.py` only
Edit: `shadow_run.py` only (CONNECT and DATES cells; fix errors there only)

## Human first
- In the CONNECT cell, paste the lines you normally use to connect to Snowflake so `conn` exists
  (a snowflake.connector connection or a Snowpark session both work).
- Set DATES: the book period must END before the quotes period STARTS.

## Agent steps
1. Run `pytest` (all tests must pass before running the script).
2. Human runs the cells in order. If a cell errors, the agent reads the error and fixes ONLY
   `shadow_run.py`. If the error is inside merc_conf/, stop and report it.

## Human check
- Printed summary shows High/Medium/Low shares and few errors.
- Open 5 Low rows in the CSV; the `reason` should make sense.

Done when the CSV exists. Append the tier shares to PROGRESS.md.
