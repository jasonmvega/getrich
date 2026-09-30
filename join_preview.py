"""JOIN preview. Students should annotate the clauses before running it."""
import sqlite3
from db_location import get_db_path

DB = get_db_path()
query = """
SELECT prices.ticker,
       prices.trade_date,
       prices.close,
       trades.side,
       trades.quantity,
       trades.trade_price
FROM prices
JOIN trades
  ON prices.ticker = trades.ticker
 AND prices.trade_date = trades.trade_date
ORDER BY prices.trade_date;
"""

# above it will select the following regarding prices, ticker, 
# trade date, closing price, and it will select the following regarding side (idk), quantity, and trading price
# it will then pull all the variables above from prices
# it will join the trade "channel"
# it will join ticker prices to ticker trades
# it will join trade date prices to trade date trades
# it will organize them by trade date prices


with sqlite3.connect(DB) as con:
    rows = con.execute(query).fetchall()
print(f"JOIN returned {len(rows)} rows")
for row in rows:
    print(row)
