import sqlite3

DATABASE_FILE = "trading.db"


def create_database() -> None:
    """Create the prices table if it does not already exist."""
    connection = sqlite3.connect(DATABASE_FILE)

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
