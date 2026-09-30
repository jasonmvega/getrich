"""Pull REAL historical daily stock bars from Alpaca and save them to SQLite.

This is the recovery/helper path for students who do not already have many
rows in their prices table. It uses Alpaca's current alpaca-py SDK.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

from alpaca_credentials import get_alpaca_credentials
from db_location import get_db_path


def ensure_prices_table(con):
    """Create prices if needed; safely upgrade the older Day 1 table if it exists."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL NOT NULL,
            volume INTEGER
        )
    """)

    existing = {row[1] for row in con.execute("PRAGMA table_info(prices)")}
    # Old Day 1 databases had id/ticker/trade_date/close/volume only.
    for name, sql_type in (("open", "REAL"), ("high", "REAL"), ("low", "REAL")):
        if name not in existing:
            con.execute(f"ALTER TABLE prices ADD COLUMN {name} {sql_type}")

    # Helpful for queries. Non-unique so it will not fail if an old DB already contains duplicates.
    con.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, trade_date)")


def save_or_update_bar(con, ticker, trade_date, open_price, high, low, close, volume):
    old = con.execute(
        "SELECT rowid FROM prices WHERE ticker = ? AND trade_date = ? LIMIT 1",
        (ticker, trade_date),
    ).fetchone()

    if old:
        con.execute("""
            UPDATE prices
            SET open = ?, high = ?, low = ?, close = ?, volume = ?
            WHERE rowid = ?
        """, (open_price, high, low, close, volume, old[0]))
        return "updated"

    con.execute("""
        INSERT INTO prices (ticker, trade_date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, trade_date, open_price, high, low, close, volume))
    return "inserted"


def pull_prices(symbols, days=180):
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
    except ImportError as exc:
        raise SystemExit(
            "alpaca-py is not installed. Run: pip install alpaca-py\n"
            "Then run this script again."
        ) from exc

    api_key, secret_key = get_alpaca_credentials()
    client = StockHistoricalDataClient(api_key, secret_key)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )

    print(f"Requesting daily bars for {', '.join(symbols)} from Alpaca...")
    bars = client.get_stock_bars(request)
    df = bars.df.reset_index()

    if df.empty:
        print("Alpaca returned 0 rows. Check the symbols, credentials, and date range.")
        return 0

    db = get_db_path()
    print(f"Saving to: {db}")
    inserted = updated = 0
    with sqlite3.connect(db) as con:
        ensure_prices_table(con)
        for _, row in df.iterrows():
            timestamp = row["timestamp"]
            trade_date = timestamp.date().isoformat() if hasattr(timestamp, "date") else str(timestamp)[:10]
            result = save_or_update_bar(
                con,
                str(row["symbol"]).upper(),
                trade_date,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                int(row["volume"]),
            )
            if result == "inserted": inserted += 1
            else: updated += 1

    print(f"Done: {inserted} rows inserted, {updated} existing rows updated.")
    return inserted + updated


if __name__ == "__main__":
    raw = input("Ticker(s), comma separated (example: AAPL,NVDA): ").strip()
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    if not symbols:
        raise SystemExit("Enter at least one ticker.")
    raw_days = input("Calendar days of history [180]: ").strip()
    days = int(raw_days) if raw_days else 180
    pull_prices(symbols, days)
    print("Next: run data_audit.py, then begin the paper-first SQL practice.")
