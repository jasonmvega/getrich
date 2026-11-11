import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

# =========================
# LOAD DATABASE
# =========================

conn = sqlite3.connect("trading.db")

df = pd.read_sql_query("""
    SELECT ticker, recorded_at, price
    FROM prices
    ORDER BY ticker, recorded_at
""", conn)

conn.close()

print("Total database rows:", len(df))

# =========================
# CLEAN DATA
# =========================

df["recorded_at"] = pd.to_datetime(df["recorded_at"])

df = df.sort_values(["ticker", "recorded_at"])

# Make sure price is numeric
df["price"] = pd.to_numeric(df["price"])

# =========================
# CREATE PREDICTORS
# =========================

# Today's percentage return
df["today_return"] = (
    df.groupby("ticker")["price"]
    .pct_change() * 100
)

# Return over the previous 5 trading days
df["return_5day"] = (
    df.groupby("ticker")["price"]
    .pct_change(5) * 100
)

# Return over the previous 20 trading days
df["return_20day"] = (
    df.groupby("ticker")["price"]
    .pct_change(20) * 100
)

# 5-day moving average
df["ma_5"] = (
    df.groupby("ticker")["price"]
    .transform(lambda x: x.rolling(5).mean())
)

# Difference between today's price and 5-day moving average
df["distance_from_ma5"] = (
    (df["price"] - df["ma_5"]) / df["ma_5"]
) * 100

# =========================
# CREATE RESPONSE
# =========================

# Tomorrow's percentage return
df["next_day_return"] = (
    df.groupby("ticker")["price"]
    .shift(-1) / df["price"] - 1
) * 100

# =========================
# SELECT PREDICTORS
# =========================

predictors = [
    "today_return",
    "return_5day",
    "return_20day",
    "distance_from_ma5"
]

# Remove rows that do not have enough previous data
# or do not have a next-day return
df = df.dropna(
    subset=predictors + ["next_day_return"]
)

print("Rows available for regression:", len(df))

# =========================
# TRAIN / TEST SPLIT
# =========================

# Use the first 80% of the data for training
# and the last 20% for testing.

df = df.sort_values(["recorded_at", "ticker"])

split = int(len(df) * 0.80)

train = df.iloc[:split]
test = df.iloc[split:]

X_train = train[predictors]
y_train = train["next_day_return"]

X_test = test[predictors]
y_test = test["next_day_return"]

# =========================
# CREATE LINEAR REGRESSION
# =========================

model = LinearRegression()

model.fit(X_train, y_train)

# =========================
# MAKE PREDICTIONS
# =========================

predictions = model.predict(X_test)

r_squared = r2_score(y_test, predictions)

# =========================
# RESULTS
# =========================

print()
print("=" * 50)
print("LINEAR REGRESSION RESULTS")
print("=" * 50)

print()

print("One predicted next-day return:")
print(f"{predictions[-1]:.4f}%")

print()

print("Intercept:")
print(f"{model.intercept_:.6f}")

print()

print("Coefficients:")

for predictor, coefficient in zip(
    predictors,
    model.coef_
):
    print(
        f"{predictor}: {coefficient:.6f}"
    )

print()

print("R-squared:")
print(f"{r_squared:.6f}")

print()

print("=" * 50)
print("PREDICTOR MEANINGS")
print("=" * 50)

print("today_return = today's percentage price change")
print("return_5day = percentage price change over 5 days")
print("return_20day = percentage price change over 20 days")
print("distance_from_ma5 = today's price compared with 5-day average")

print()
print("Response = next_day_return")
print("This is tomorrow's percentage change in closing price.")