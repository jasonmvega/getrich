"""REFERENCE/teacher check. Students should write required SQL on paper first."""
import sqlite3
from db_location import get_db_path

DB = get_db_path()
queries = {
    "count_trades": "SELECT COUNT(*) FROM trades;",
    "count_by_ticker": "SELECT ticker, COUNT(*) FROM trades GROUP BY ticker;",
    "avg_price_by_ticker": "SELECT ticker, AVG(trade_price) FROM trades GROUP BY ticker;",
    "min_max_by_ticker": "SELECT ticker, MIN(trade_price), MAX(trade_price) FROM trades GROUP BY ticker;",
    "total_quantity": "SELECT ticker, SUM(quantity) FROM trades GROUP BY ticker;",
    "having_more_than_one": "SELECT ticker, COUNT(*) FROM trades GROUP BY ticker HAVING COUNT(*) > 1;",
}

with sqlite3.connect(DB) as con:
    for name, query in queries.items():
        print(f"\n--- {name} ---")
        for row in con.execute(query):
            print(row)
