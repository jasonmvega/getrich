"""Fallback ONLY when a student's Alpaca paper account has no usable filled orders today."""
import sqlite3
from db_location import get_db_path

DB = get_db_path()
sample_trades = [
    (None, "AAPL", "2026-01-06", "BUY", 5, 215.12, "filled"),
    (None, "AAPL", "2026-01-10", "SELL", 5, 219.40, "filled"),
    (None, "NVDA", "2026-01-07", "BUY", 2, 145.20, "filled"),
    (None, "MSFT", "2026-01-08", "BUY", 3, 418.55, "filled"),
    (None, "MSFT", "2026-01-12", "SELL", 1, 421.10, "filled"),
]

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
    con.executemany("""
        INSERT INTO trades
        (alpaca_order_id, ticker, trade_date, side, quantity, trade_price, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sample_trades)
print(f"5 fallback trade rows inserted into {DB}")
