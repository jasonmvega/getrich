"""
Type your required JOIN challenge below, then run this file.

join_preview.py shows a worked JOIN example -- that one is given to you
for free, don't edit it. This file is for the required variation you
write yourself: modify the join_preview.py query to show only BUY
trades, ordered by trade_date.
"""
import sqlite3
from db_location import get_db_path

DB = get_db_path()

# Write your query on paper first, THEN replace the line below with it.
query = """
SELECT prices.ticker,
       trades.trade_date,
       prices.price,
       trades.side,
       trades.quantity,
       trades.trade_price
FROM prices
JOIN trades
  ON prices.ticker = trades.ticker
WHERE trades.side = 'BUY'
ORDER BY trades.trade_date;
"""

if query is None:
    raise SystemExit("Write your query on paper first, then replace `query = None` above.")

with sqlite3.connect(DB) as con:
    rows = con.execute(query).fetchall()

print(f"Database: {DB}")
print(f"Rows returned: {len(rows)}")
for row in rows:
    print(row)
