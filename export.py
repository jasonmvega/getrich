
import sqlite3
from pathlib import Path

import pandas as pd


DB_URI = (
    "file:////192.168.1.95/CS-CLASSROOM/"
    "intraday_5m.sqlite?mode=ro&immutable=1"
)

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "msft_2024_5min.csv"


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("Connecting to historical database...")

    connection = sqlite3.connect(
        DB_URI,
        uri=True,
        timeout=30
    )

    try:

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

        df = pd.read_sql_query(
            query,
            connection
        )

    finally:
        connection.close()

    if df.empty:
        raise ValueError(
            "No MSFT historical records were found."
        )

    df["ts_utc"] = pd.to_datetime(
        df["ts_utc"],
        utc=True
    )

    for col in ["high", "low", "close"]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=["high", "low", "close"]
    )

    df = df.drop_duplicates(
        subset="ts_utc"
    )

    df = df.sort_values("ts_utc")

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nEXPORT COMPLETE")
    print("------------------------------")
    print("Records:", len(df))
    print("File:", OUTPUT_FILE)
    print("First timestamp:", df["ts_utc"].min())
    print("Last timestamp:", df["ts_utc"].max())


if __name__ == "__main__":
    main()
