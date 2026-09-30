# How to run this kit (for humans)

The scoring math is already written and tested. The agent only fills in names from your environment
(Verisk dict keys, Snowflake tables) and helps run the notebook. Method: *MERC Confidence Score: Four-Signal Method*.

## 0 · Set up (once)
1. Copy this folder into your repo root.
2. `pip install numpy pandas pytest` (plus your usual Snowflake package).
3. Run `pytest`. Expected: **12 passed, 3 failed**. The 3 failures are the P1–P3 gates.

## 1 · One card per session
For each card in order, open a **new** Copilot chat (agent mode), pick the model, and type:

> Do tasks/P1_verisk_keys.md

Do the card's "Human first" part before starting the chat. Approve the test run. When it's done,
check that PROGRESS.md got a new line, then close the chat.

| Card | What the agent does | You provide |
|---|---|---|
| P1 | Maps Verisk dict keys | Two printed Verisk dicts pasted into a fixture |
| P2 | Fills the book query | Table and column names for MERC, sq ft, date, bound flag |
| P3 | Fills the quotes query | Quotes table and column names |
| P4 | Helps run `shadow_run.py` | Your Snowflake connection lines, the dates |

After P3, `pytest` should show **15 passed**.

## 2 · Decisions only you make
- **Which Verisk field is the Property Confidence Score.** The kit uses the **iScore of the prefill valuation**
  (`mapping.get_pcs`). Change that one line if it's something else.
- **Tolerances, tier cutoffs, PCS risk values**: `merc_conf/config.py`. Tune after shadow mode, not in agent sessions.

## 3 · Notes
- Prefill and final both use `rebuild_cost_custom` (final = same call + `valuation_id` + member overrides),
  so the two are comparable. The address-only `rebuild_cost` call can return a different iScore.
- `shadow_run.py` uses `# %%` cells: open it in VS Code and click "Run Cell".
- If an agent session goes off track, discard its changes (`git checkout -- .`) and rerun the card in a new chat.
