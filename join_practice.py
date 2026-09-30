import sqlite3
from db_location import get_db_path

DB = get_db_path()
query = """
SELECT stocks.ticker,
       relational_prices.trade_date,
       relational_prices.close
FROM stocks
JOIN relational_prices
ON stocks.stock_id = relational_prices.stock_id
ORDER BY relational_prices.trade_date;
"""
with sqlite3.connect(DB) as con:
    for row in con.execute(query):
        print(row)
