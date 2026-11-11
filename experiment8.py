
import sqlite3
import pandas as pd
import numpy as np

from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# ==========================================
# DATABASE SETTINGS
# ==========================================

DB_URI = (
    "file:////192.168.1.95/CS-CLASSROOM/"
    "intraday_5m.sqlite?mode=ro&immutable=1"
)

STOCK = "MSFT"

print("Connecting to database...")

conn = sqlite3.connect(DB_URI, uri=True)

query = """
SELECT
    symbol,
    ts_utc,
    high,
    low,
    close,
    volume
FROM bars_5m
WHERE symbol = ?
AND ts_utc >= '2022-03-01'
AND ts_utc < '2025-11-03'
ORDER BY ts_utc;
"""

df = pd.read_sql_query(
    query,
    conn,
    params=(STOCK,)
)

conn.close()

print("Database data loaded!")
print("Records retrieved:", len(df))

# ==========================================
# DATA PREPARATION
# ==========================================

df["ts_utc"] = pd.to_datetime(
    df["ts_utc"],
    utc=True
)

df = df.sort_values("ts_utc").reset_index(drop=True)

# Price range
df["price_range"] = df["high"] - df["low"]

# Original features
df["return_1"] = df["close"].pct_change(1) * 100

df["return_3"] = df["close"].pct_change(3) * 100

df["range_percent"] = (
    df["price_range"] / df["close"]
) * 100

# NEW FEATURES
# Price change over previous 30 minutes
df["return_6"] = df["close"].pct_change(6) * 100

# Price change over previous 60 minutes
df["return_12"] = df["close"].pct_change(12) * 100

# Future closing price after 3 bars (15 minutes)
df["future_close"] = df["close"].shift(-3)

df["future_ts"] = df["ts_utc"].shift(-3)

# Check that future record is exactly 15 minutes ahead
df["time_difference"] = (
    df["future_ts"] - df["ts_utc"]
)

df = df[
    df["time_difference"] == pd.Timedelta(minutes=15)
].copy()

# Target: future percentage change
df["target"] = (
    (df["future_close"] - df["close"])
    / df["close"]
) * 100

# ==========================================
# FEATURE SELECTION
# ==========================================

features = [
    "return_1",
    "return_3",
    "range_percent",
    "return_6",
    "return_12"
]

df = df.dropna(
    subset=features + ["target"]
)

print("Usable records:", len(df))

# ==========================================
# TRAINING AND TESTING
# ==========================================

test_start = pd.Timestamp(
    "2025-10-01",
    tz="UTC"
)

test_end = pd.Timestamp(
    "2025-11-01",
    tz="UTC"
)

# October testing data
test = df[
    (df["ts_utc"] >= test_start) &
    (df["ts_utc"] < test_end)
].copy()

# Long training period
# Exclude any training row whose target uses October data
train = df[
    (df["ts_utc"] < test_start) &
    (df["future_ts"] < test_start)
].copy()

print("\n=== DATASET SIZES ===")
print("Training records:", len(train))
print("Testing records:", len(test))

# ==========================================
# LINEAR REGRESSION MODEL
# ==========================================

X_train = train[features]
y_train = train["target"]

X_test = test[features]
y_test = test["target"]

model = LinearRegression()

print("\nTraining Linear Regression...")

model.fit(X_train, y_train)

predictions = model.predict(X_test)

# ==========================================
# MODEL EVALUATION
# ==========================================

mae = mean_absolute_error(
    y_test,
    predictions
)

mse = mean_squared_error(
    y_test,
    predictions
)

rmse = np.sqrt(mse)

r2 = r2_score(
    y_test,
    predictions
)

# Zero-change baseline
baseline = np.zeros(len(y_test))

baseline_mae = mean_absolute_error(
    y_test,
    baseline
)

baseline_rmse = np.sqrt(
    mean_squared_error(y_test, baseline)
)

print("\n==============================")
print("EXPERIMENT 8 RESULTS")
print("==============================")

print("MAE:", round(mae, 6))
print("MSE:", round(mse, 6))
print("RMSE:", round(rmse, 6))
print("R²:", round(r2, 6))

print("\nZERO-CHANGE BASELINE")
print("Baseline MAE:", round(baseline_mae, 6))
print("Baseline RMSE:", round(baseline_rmse, 6))

# ==========================================
# COEFFICIENTS
# ==========================================

print("\n=== MODEL COEFFICIENTS ===")

for feature, coefficient in zip(
    features,
    model.coef_
):
    print(feature, ":", coefficient)

print("Intercept:", model.intercept_)

# ==========================================
# SAVE RESULTS
# ==========================================

results = pd.DataFrame([{
    "experiment": "Experiment 8",
    "stock": STOCK,
    "training_records": len(train),
    "testing_records": len(test),
    "MAE": mae,
    "MSE": mse,
    "RMSE": rmse,
    "R2": r2,
    "baseline_MAE": baseline_mae,
    "baseline_RMSE": baseline_rmse
}])

results.to_csv(
    "experiment8_results.csv",
    index=False
)

predictions_df = pd.DataFrame({
    "timestamp": test["ts_utc"].values,
    "actual_change": y_test.values,
    "predicted_change": predictions
})

predictions_df.to_csv(
    "experiment8_predictions.csv",
    index=False
)

print("\n==============================")
print("EXPERIMENT 8 COMPLETE")
print("==============================")

print("Saved experiment8_results.csv")
print("Saved experiment8_predictions.csv")
