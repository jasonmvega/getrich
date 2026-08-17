import sqlite3

connection = sqlite3.connect("trading.db")

# Run ONE query at a time.
# Before each query, predict what you think will appear.

# QUERY 1: Show the first 10 real records saved from Alpaca.
# query = """
# SELECT id, ticker, recorded_at, price
# FROM prices
# ORDER BY recorded_at
# LIMIT 10;
# """

# QUERY 2: Show only one ticker.
# Change AAPL to a ticker that is actually in YOUR database.
query = """
SELECT id, ticker, recorded_at, price
FROM prices
WHERE ticker = 'AAPL'
ORDER BY recorded_at;
"""

# QUERY 3: Show the highest prices first.
# query = """
# SELECT ticker, recorded_at, price
# FROM prices
# ORDER BY price DESC
# LIMIT 10;
# """

# QUERY 4: Show only the ticker, date/time, and price.
# query = """
# SELECT ticker, recorded_at, price
# FROM prices
# ORDER BY recorded_at DESC
# LIMIT 10;
# """

rows = connection.execute(query).fetchall()

print(f"Rows returned: {len(rows)}")
for row in rows:
    print(row)

connection.close()
