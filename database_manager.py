import sqlite3

DATABASE_FILE = "trading.db"


def create_database() -> None:
    """Create the prices and signals tables if they do not already exist."""
    connection = sqlite3.connect(DATABASE_FILE)

    # Create prices table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            price REAL NOT NULL
        )
        """
    )

    # Create signals table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()
    
def save_price(ticker: str, recorded_at: str, price: float) -> None:
    """Save one stock-price record."""
    connection = sqlite3.connect(DATABASE_FILE)

    connection.execute(
        """
        INSERT INTO prices (ticker, recorded_at, price)
        VALUES (?, ?, ?)
        """,
        (ticker, recorded_at, price),
    )

    connection.commit()
    connection.close()

def save_signal(
    ticker: str,
    recorded_at: str,
    decision: str,
    reason: str
) -> None:
    """Save a trading signal to the signals table."""
    connection = sqlite3.connect(DATABASE_FILE)

    connection.execute(
        """
        INSERT INTO signals (ticker, recorded_at, decision, reason)
        VALUES (?, ?, ?, ?)
        """,
        (ticker, recorded_at, decision, reason),
    )

    connection.commit()
    connection.close()
