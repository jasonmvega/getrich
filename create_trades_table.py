"""
OPTIONAL PRACTICE ONLY.

You do not need to run this file. import_alpaca_trade_history.py and
fallback_trades.py both already create the trades table themselves
(CREATE TABLE IF NOT EXISTS), so the table will exist either way.

Run this only if you want extra practice typing a CREATE TABLE
statement by hand before those scripts do it for you.
"""
import sqlite3
from db_location import get_db_path

DB = get_db_path()
with sqlite3.connect(DB) as con:
    con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alpaca_order_id TEXT UNIQUE,
            ticker TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            trade_price REAL NOT NULL,
            status TEXT
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_trades_ticker_date ON trades(ticker, trade_date)")
print(f"trades table ready in {DB}")
