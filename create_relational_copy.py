"""Rebuild a clean relational learning copy: stocks + relational_prices."""
import sqlite3
from db_location import get_db_path

DB = get_db_path()

# Column names in the source `prices` table that might hold the trade date.
# Add to this list if your actual column name isn't here.
DATE_COLUMN_CANDIDATES = ["trade_date", "date", "price_date", "trading_date", "dt", "recorded_at"]

# Column name in `prices` that holds the closing price.
PRICE_COLUMN_CANDIDATES = ["close", "price", "close_price"]


def find_price_column(con):
    """Look at the real schema of `prices` and figure out which column holds the price."""
    columns = [row[1] for row in con.execute("PRAGMA table_info(prices)").fetchall()]

    for candidate in PRICE_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate

    raise RuntimeError(
        "Could not find a price column in `prices`. "
        f"Actual columns are: {columns}. "
        "Add the correct name to PRICE_COLUMN_CANDIDATES at the top of this script."
    )


def find_date_column(con):
    """Look at the real schema of `prices` and figure out which column holds the date."""
    columns = [row[1] for row in con.execute("PRAGMA table_info(prices)").fetchall()]

    for candidate in DATE_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate

    raise RuntimeError(
        "Could not find a date column in `prices`. "
        f"Actual columns are: {columns}. "
        "Add the correct name to DATE_COLUMN_CANDIDATES at the top of this script."
    )


with sqlite3.connect(DB) as con:
    con.execute("PRAGMA foreign_keys = ON")

    source_date_col = find_date_column(con)
    source_price_col = find_price_column(con)
    print(f"Using '{source_date_col}' as the date column from `prices`.")
    print(f"Using '{source_price_col}' as the price column from `prices`.")

    con.execute("DROP TABLE IF EXISTS relational_prices")
    con.execute("DROP TABLE IF EXISTS stocks")

    con.execute("""
        CREATE TABLE stocks (
            stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            company_name TEXT
        )
    """)
    con.execute("""
        CREATE TABLE relational_prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            trade_date TEXT NOT NULL,
            close REAL NOT NULL,
            FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
        )
    """)

    for (ticker,) in con.execute("SELECT DISTINCT ticker FROM prices"):
        con.execute("INSERT INTO stocks (ticker) VALUES (?)", (ticker,))

    price_rows = con.execute(
        f"SELECT ticker, {source_date_col}, {source_price_col} FROM prices"
    ).fetchall()

    for ticker, trade_date, close in price_rows:
        stock_id = con.execute(
            "SELECT stock_id FROM stocks WHERE ticker = ?", (ticker,)
        ).fetchone()[0]
        con.execute(
            "INSERT INTO relational_prices (stock_id, trade_date, close) VALUES (?, ?, ?)",
            (stock_id, trade_date, close),
        )

print(f"Relational learning copy rebuilt in {DB}")