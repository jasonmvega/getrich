import sqlite3

DATABASE_FILE = "trading.db"

connection = sqlite3.connect(DATABASE_FILE)


# QUESTION 6
# How many prices are saved?
query = """
SELECT COUNT(*)
FROM prices;
"""

print("\nQUESTION 6: How many prices are saved?")
print(connection.execute(query).fetchone()[0])


# QUESTION 7
# How many total signals are saved?
query = """
SELECT COUNT(*)
FROM signals;
"""

print("\nQUESTION 7: How many total signals are saved?")
print(connection.execute(query).fetchone()[0])


# QUESTION 8
# How many BUY, SELL, and HOLD signals occurred?
query = """
SELECT decision, COUNT(*)
FROM signals
GROUP BY decision;
"""

print("\nQUESTION 8: How many BUY, SELL, and HOLD signals occurred?")
for row in connection.execute(query):
    print(row)


# QUESTION 9
# What is the highest saved price?
query = """
SELECT MAX(price)
FROM prices;
"""

print("\nQUESTION 9: What is the highest saved price?")
print(connection.execute(query).fetchone()[0])


# QUESTION 10
# What is the lowest saved price?
query = """
SELECT MIN(price)
FROM prices;
"""

print("\nQUESTION 10: What is the lowest saved price?")
print(connection.execute(query).fetchone()[0])


# QUESTION 11
# What is the average saved price?
query = """
SELECT AVG(price)
FROM prices;
"""

print("\nQUESTION 11: What is the average saved price?")
print(connection.execute(query).fetchone()[0])


# QUESTION 12
# What are the five most recent signals?
query = """
SELECT ticker, recorded_at, decision, reason
FROM signals
ORDER BY recorded_at DESC
LIMIT 5;
"""

print("\nQUESTION 12: What are the five most recent signals?")
for row in connection.execute(query):
    print(row)


# QUESTION 13
# Which ticker has the most saved prices?
query = """
SELECT ticker, COUNT(*) AS price_count
FROM prices
GROUP BY ticker
ORDER BY price_count DESC
LIMIT 1;
"""

print("\nQUESTION 13: Which ticker has the most saved prices?")
print(connection.execute(query).fetchone())


# QUESTION 14
# Which ticker has the most BUY signals?
query = """
SELECT ticker, COUNT(*) AS buy_count
FROM signals
WHERE decision = 'BUY'
GROUP BY ticker
ORDER BY buy_count DESC
LIMIT 1;
"""

print("\nQUESTION 14: Which ticker has the most BUY signals?")
print(connection.execute(query).fetchone())


connection.close()