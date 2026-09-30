"""Connect to the student's Alpaca PAPER account and import filled order history.

For this database lesson we treat each filled Alpaca order as one trade record.
This is sufficient for SQL practice; it is not execution-level fill accounting.
"""
import sqlite3

from alpaca_credentials import get_alpaca_credentials
from db_location import get_db_path


def text_value(value):
    return value.value if hasattr(value, "value") else str(value)


def import_orders():
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
    except ImportError as exc:
        raise SystemExit("alpaca-py is not installed. Run: pip install alpaca-py") from exc

    key, secret = get_alpaca_credentials()
    client = TradingClient(key, secret, paper=True)

    # CLOSED can contain filled and canceled orders, so we filter to records with filled_at/fill qty.
    request = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500)
    orders = client.get_orders(filter=request)

    DB = get_db_path()
    imported = updated = skipped = 0
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

        for order in orders:
            filled_at = getattr(order, "filled_at", None)
            filled_qty = getattr(order, "filled_qty", None)
            if filled_at is None or filled_qty in (None, "0", 0):
                skipped += 1
                continue

            order_id = str(order.id)
            ticker = str(order.symbol).upper()
            trade_date = filled_at.date().isoformat() if hasattr(filled_at, "date") else str(filled_at)[:10]
            side = text_value(order.side).upper()
            quantity = float(filled_qty)
            trade_price = float(getattr(order, "filled_avg_price", 0) or 0)
            status = text_value(order.status)

            existing = con.execute(
                "SELECT trade_id FROM trades WHERE alpaca_order_id = ?", (order_id,)
            ).fetchone()
            if existing:
                con.execute("""
                    UPDATE trades
                    SET ticker=?, trade_date=?, side=?, quantity=?, trade_price=?, status=?
                    WHERE alpaca_order_id=?
                """, (ticker, trade_date, side, quantity, trade_price, status, order_id))
                updated += 1
            else:
                con.execute("""
                    INSERT INTO trades
                    (alpaca_order_id, ticker, trade_date, side, quantity, trade_price, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (order_id, ticker, trade_date, side, quantity, trade_price, status))
                imported += 1

    print(f"Database: {DB}")
    print(f"Filled Alpaca orders imported: {imported}; updated: {updated}; non-filled closed orders skipped: {skipped}")
    if imported + updated == 0:
        print("No filled order history was available. Use fallback_trades.py ONLY so you can continue SQL practice today.")


if __name__ == "__main__":
    import_orders()
