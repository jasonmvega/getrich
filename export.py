
import sqlite3
import pandas as pd
from pathlib import Path

# School database
DB_URI = (
    "file:////192.168.1.95/CS-CLASSROOM/"
    "intraday_5m.sqlite?mode=ro&immutable=1"
)

# Output location
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "msft_2024_5min.csv"

print("Connecting to historical database...")

connection = sqlite3.connect(DB_URI, uri=True)

query = """
SELECT
    ts_utc,
    high,
    low,
    close
FROM bars_5m
WHERE symbol = 'MSFT'
  AND ts_utc >= '2024-01-01'
  AND ts_utc < '2025-01-01'
ORDER BY ts_utc ASC;
"""

df = pd.read_sql_query(query, connection)

connection.close()

if df.empty:
    raise ValueError("No MSFT historical records were found.")

df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)

df = df.drop_duplicates(subset="ts_utc")
df = df.dropna(subset=["high", "low", "close"])

df.to_csv(OUTPUT_FILE, index=False)

print("\nEXPORT COMPLETE")
print("------------------------------")
print(f"Records exported: {len(df)}")
print(f"Output file: {OUTPUT_FILE}")
print(f"First record: {df['ts_utc'].min()}")
print(f"Last record: {df['ts_utc'].max()}")
