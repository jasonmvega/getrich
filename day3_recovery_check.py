"""Day 3 triage: tells each student exactly what to do next."""
import sqlite3
from db_location import get_db_path

DB = get_db_path()
print(f"Using database: {DB}")

try:
    with sqlite3.connect(DB) as con:
        prices = con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
except sqlite3.Error:
    prices = None

if prices is None or prices == 0:
    print("STATUS: RED")
    print("No usable prices table/rows were found.")
    print("Run recovery_import_prices.py. It connects directly to Alpaca and builds/adds the real price rows.")
elif prices < 20:
    print("STATUS: YELLOW")
    print(f"Only {prices} price rows found.")
    print("Run recovery_import_prices.py to add more historical bars, then run this check again.")
else:
    print("STATUS: GREEN")
    print(f"{prices} price rows found. Do NOT redo Day 2. Move to the SQL review and trade-history step.")
