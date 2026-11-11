import sqlite3
import csv

DB_URI = (
    "file:////192.168.1.95/CS-CLASSROOM/"
    "intraday_5m.sqlite?mode=ro&immutable=1"
)

STOCK = "MSFT"

conn = sqlite3.connect(DB_URI, uri=True)
cursor = conn.cursor()

cursor.execute("""
    SELECT
        MIN(ts_utc),
        MAX(ts_utc),
        COUNT(*)
    FROM bars_5m
    WHERE symbol = ?
""", (STOCK,))

result = cursor.fetchone()

with open("database_coverage.csv", "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["symbol", "first_record", "last_record", "total_records"])
    writer.writerow([STOCK, *result])

conn.close()

print("Saved MSFT database coverage to database_coverage.csv")