"""
Type ONE required JOIN query at a time below, then run this file.
Do this 3 times total, once per required challenge -- replace the query,
save, run, screenshot the output, then move to the next challenge.

Run create_relational_copy.py first -- it builds stocks and
relational_prices from your existing prices table.

IMPORTANT: use relational_prices, not prices, in every query today.
prices does not have a stock_id column -- only relational_prices does.

Your 3 required challenges (see the Day 4 Material for full wording):
  1. JOIN stocks and relational_prices, showing only rows above a
     close price you choose.
  2. JOIN stocks and relational_prices, GROUP BY to count price rows
     per ticker.
  3. One original JOIN query using stocks and relational_prices.
"""
import sqlite3
from db_location import get_db_path

DB = get_db_path()

# Replace ONLY the SQL below after you have written/predicted it on paper.
# This starts as the worked example from the Material (given for free).
query = """
SELECT stocks.ticker,
       AVG(relational_prices.close) AS avg_close
FROM stocks
JOIN relational_prices
  ON stocks.stock_id = relational_prices.stock_id
GROUP BY stocks.ticker
ORDER BY avg_close DESC;
"""

with sqlite3.connect(DB) as con:
    rows = con.execute(query).fetchall()

print(f"Database: {DB}")
print(f"Rows returned: {len(rows)}")
for row in rows[:100]:
    print(row)
