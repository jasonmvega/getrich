
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

# Retrieve only MSFT data needed for this experiment
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

df = pd.read_sql_query(query, conn, params=(STOCK,))

conn.close()

print("Database data loaded!")
print("Records retrieved:", len(df))

# ==========================================
# DATA PREPARATION
# ==========================================

df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)

df = df.sort_values("ts_utc").reset_index(drop=True)

# Price range
df["price_range"] = df["high"] - df["low"]

# Historical percentage returns
df["return_1"] = df["close"].pct_change() * 100

df["return_3"] = (
    df["close"].pct_change(periods=3) * 100
)

# Percentage price range
df["range_percent"] = (
    df["price_range"] / df["close"]
) * 100

# Future closing price after 3 bars (15 minutes)
df["future_close"] = df["close"].shift(-3)

df["future_ts"] = df["ts_utc"].shift(-3)

# Make sure the future record is exactly 15 minutes ahead
df["time_difference"] = (
    df["future_ts"] - df["ts_utc"]
)

df = df[
    df["time_difference"] == pd.Timedelta(minutes=15)
].copy()

# Target: percentage change in the next 15 minutes
df["target"] = (
    (df["future_close"] - df["close"])
    / df["close"]
) * 100

# Remove incomplete rows
features = [
    "return_1",
    "return_3",
    "range_percent"
]

df = df.dropna(subset=features + ["target"])

print("Usable records:", len(df))

# ==========================================
# TRAINING AND TESTING PERIODS
# ==========================================

test_start = pd.Timestamp("2025-10-01", tz="UTC")
test_end = pd.Timestamp("2025-11-01", tz="UTC")

jan_start = pd.Timestamp("2025-01-01", tz="UTC")

# October 2025 testing data
test = df[
    (df["ts_utc"] >= test_start) &
    (df["ts_utc"] < test_end)
].copy()

# Training data must have its future target
# before October begins.
long_train = df[
    (df["ts_utc"] < test_start) &
    (df["future_ts"] < test_start)
].copy()

# January-September comparison training data
short_train = long_train[
    long_train["ts_utc"] >= jan_start
].copy()

print("\n=== DATASET SIZES ===")
print("Long training:", len(long_train))
print("Short training:", len(short_train))
print("October testing:", len(test))

# ==========================================
# MODEL EVALUATION
# ==========================================

def evaluate_model(name, train_data, test_data):

    X_train = train_data[features]
    y_train = train_data["target"]

    X_test = test_data[features]
    y_test = test_data["target"]

    model = LinearRegression()

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)

    mse = mean_squared_error(y_test, predictions)

    rmse = np.sqrt(mse)

    r2 = r2_score(y_test, predictions)

    # Zero-change baseline
    baseline = np.zeros(len(y_test))

    baseline_mae = mean_absolute_error(
        y_test, baseline
    )

    baseline_rmse = np.sqrt(
        mean_squared_error(y_test, baseline)
    )

    print("\n==============================")
    print(name)
    print("==============================")

    print("MAE:", round(mae, 6))
    print("MSE:", round(mse, 6))
    print("RMSE:", round(rmse, 6))
    print("R²:", round(r2, 6))

    print("\nZero-change baseline:")
    print("Baseline MAE:", round(baseline_mae, 6))
    print("Baseline RMSE:", round(baseline_rmse, 6))

    print("\nCoefficients:")
    for feature, coefficient in zip(
        features, model.coef_
    ):
        print(feature, ":", coefficient)

    print("Intercept:", model.intercept_)

    return {
        "experiment": name,
        "training_records": len(train_data),
        "testing_records": len(test_data),
        "MAE": mae,
        "MSE": mse,
        "RMSE": rmse,
        "R2": r2,
        "baseline_MAE": baseline_mae,
        "baseline_RMSE": baseline_rmse
    }, predictions


# ==========================================
# RUN BOTH EXPERIMENTS
# ==========================================

results = []

result_long, predictions_long = evaluate_model(
    "EXPERIMENT 7A - LONG TRAINING",
    long_train,
    test
)

results.append(result_long)

result_short, predictions_short = evaluate_model(
    "EXPERIMENT 7B - JANUARY TRAINING",
    short_train,
    test
)

results.append(result_short)

# ==========================================
# SAVE RESULTS
# ==========================================

results_df = pd.DataFrame(results)

results_df.to_csv(
    "experiment7_results.csv",
    index=False
)

predictions_df = pd.DataFrame({
    "timestamp": test["ts_utc"].values,
    "actual_change": test["target"].values,
    "long_training_prediction": predictions_long,
    "short_training_prediction": predictions_short
})

predictions_df.to_csv(
    "experiment7_predictions.csv",
    index=False
)

print("\n==============================")
print("EXPERIMENT 7 COMPLETE")
print("==============================")

print("Saved experiment7_results.csv")
print("Saved experiment7_predictions.csv")
