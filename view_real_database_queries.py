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
# query = """
# SELECT id, ticker, recorded_at, price
# FROM prices
# WHERE ticker = 'AAPL'
# ORDER BY recorded_at;
# """

# QUERY 3: Show the highest prices first.
query = """
SELECT ticker, recorded_at, price
FROM prices
ORDER BY price DESC
LIMIT 10;
"""

# QUERY 4: Show only the ticker, date/time, and price.
# query = """
# SELECT ticker, recorded_at, price
# FROM prices
# ORDER BY recorded_at DESC
# LIMIT 10;
# """

# QUERY 5: Show only the ticker and price columns.
# query = """
# SELECT ticker, price
# FROM prices
# LIMIT 10;
# """

# QUERY 6: Find the average price for each ticker.
# query = """
# SELECT ticker, AVG(price)
# FROM prices
# GROUP BY ticker
# ORDER BY AVG(price) DESC;
# """

# QUERY 7: Show average price for AAPL.
query = """
SELECT AVG(price)
FROM prices
WHERE ticker = 'AAPL';
"""

rows = connection.execute(query).fetchall()

print(f"Rows returned: {len(rows)}")
for row in rows:
    print(row)

connection.close()
