
import sqlite3
import csv
from pathlib import Path

# ==========================================
# 1. DATABASE SETTINGS
# ==========================================

DB_URI = (
    "file:////192.168.1.95/CS-CLASSROOM/"
    "intraday_5m.sqlite?mode=ro&immutable=1"
)

START_DATE = "2025-01-01"
END_DATE = "2025-11-01"  # Exclusive: includes all of October

STOCKS = ("AAPL", "MSFT")

# ==========================================
# 2. SQL QUERY: CURRENT STOCK DATA
# ==========================================

stock_sql = """
SELECT
    symbol,
    ts_utc,
    close,
    volume,
    high - low AS price_range
FROM bars_5m
WHERE symbol IN (?, ?)
  AND ts_utc >= ?
  AND ts_utc < ?
ORDER BY symbol, ts_utc;
"""

# ==========================================
# 3. SQL QUERY: FUTURE STOCK PRICES
# ==========================================

future_sql = """
WITH future_prices AS (
    SELECT
        symbol,
        ts_utc,
        LEAD(close, 3) OVER (
            PARTITION BY symbol
            ORDER BY ts_utc
        ) AS future_close,

        LEAD(ts_utc, 3) OVER (
            PARTITION BY symbol
            ORDER BY ts_utc
        ) AS future_timestamp

    FROM bars_5m

    WHERE symbol IN (?, ?)
      AND ts_utc >= ?
      AND ts_utc < ?
)

SELECT
    symbol,
    ts_utc,
    future_close

FROM future_prices

WHERE ts_utc >= ?
  AND ts_utc < ?
  AND future_close IS NOT NULL
  AND future_timestamp IS NOT NULL

  -- Only keep records exactly 15 minutes apart
  AND ABS(
      (julianday(future_timestamp) - julianday(ts_utc))
      * 1440 - 15
  ) < 0.01

ORDER BY symbol, ts_utc;
"""

# ==========================================
# 4. EXPORT FUNCTION
# ==========================================

def export_query(connection, sql, params, filename):

    cursor = connection.cursor()

    cursor.execute(sql, params)

    rows = cursor.fetchall()

    column_names = [
        description[0]
        for description in cursor.description
    ]

    with open(filename, "w", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow(column_names)
        writer.writerows(rows)

    print(f"{filename}: {len(rows)} records exported.")

    return len(rows)


# ==========================================
# 5. MAIN PROGRAM
# ==========================================

def main():

    print("Connecting to database...")

    try:
        connection = sqlite3.connect(DB_URI, uri=True)

        print("Connected successfully!")

        # Include November 1 in the source data so
        # late October records can still get future prices.
        source_end = "2025-11-02"

        # Export current stock data
        stock_count = export_query(
            connection,
            stock_sql,
            (
                STOCKS[0],
                STOCKS[1],
                START_DATE,
                END_DATE
            ),
            "stock_data.csv"
        )

        # Export future stock prices
        future_count = export_query(
            connection,
            future_sql,
            (
                STOCKS[0],
                STOCKS[1],
                START_DATE,
                source_end,
                START_DATE,
                END_DATE
            ),
            "future_stock_prices.csv"
        )

        connection.close()

        print("\n=== EXTRACTION COMPLETE ===")
        print("Stocks:", STOCKS)
        print("Current stock records:", stock_count)
        print("Future price records:", future_count)

        if future_count == 0:
            print(
                "\nWARNING: No future prices were exported. "
                "Check the database timestamps and stock symbols."
            )

    except sqlite3.Error as error:
        print("Database error:", error)

    except Exception as error:
        print("Error:", error)


if __name__ == "__main__":
    main()
