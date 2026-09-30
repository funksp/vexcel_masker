# %% [markdown]
# # MERC confidence · shadow run
# Scores past quotes and writes the results. Changes nothing in the quote flow.
# Edit only the CONNECT and DATES cells.

# %% CONNECT (paste how you normally connect to Snowflake; must define `conn`)
conn = None

# %% DATES ('YYYY-MM-DD'; the book period must end before the quote period starts)
BOOK_START, BOOK_END = "2025-01-01", "2026-07-01"
QUOTE_START, QUOTE_END = "2026-07-01", "2026-10-01"

# %% 1 · Neighborhood reference from the book
from merc_conf import data, h3_ref, shadow

book = data.load_book(conn, BOOK_START, BOOK_END)
ref = h3_ref.build_reference(book)
print(f"{len(book):,} book rows -> {len(ref):,} reference cells")

# %% 2 · Score the quotes
quotes = data.load_quotes(conn, QUOTE_START, QUOTE_END)
results = shadow.score_frame(quotes, ref)
print(shadow.summary(results))

# %% 3 · Save
results.to_csv("shadow_results.csv", index=False)
ref.to_csv("neighborhood_reference.csv", index=False)

# %% 4 · (Optional) Score one address live, like the Verisk notebook examples
# from merc_conf import pipeline
# from verisk_api_wrapper import characteristic
# cells = data.cells_for_house(conn, "HOUSE_ID")
# r, pre, fin = pipeline.score_live(client, "street", "city", "ST", "zip", cells, h3_ref.index(ref),
#                                   overrides=[characteristic("GENERALINFO", totalfinishedsqft=1500)])
# print(r.tier, round(r.confidence, 3), r.reason, r.flags)
