
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
    close
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

# Calculate price range
df["price_range"] = df["high"] - df["low"]

# Feature 1: Previous 5-minute percentage return
df["return_1"] = (
    df["close"].pct_change(1) * 100
)

# Feature 2: Percentage price range
df["range_percent"] = (
    df["price_range"] / df["close"]
) * 100

# Future closing price after 3 bars (15 minutes)
df["future_close"] = df["close"].shift(-3)

df["future_ts"] = df["ts_utc"].shift(-3)

# Verify future record is exactly 15 minutes ahead
df["time_difference"] = (
    df["future_ts"] - df["ts_utc"]
)

df = df[
    df["time_difference"] == pd.Timedelta(minutes=15)
].copy()

# Target: Future percentage change
df["target"] = (
    (df["future_close"] - df["close"])
    / df["close"]
) * 100

# ==========================================
# FEATURE SELECTION
# ==========================================

features = [
    "return_1",
    "range_percent"
]

df = df.dropna(
    subset=features + ["target"]
)

print("Usable records:", len(df))

# ==========================================
# DATE SETTINGS
# ==========================================

start_2022 = pd.Timestamp(
    "2022-03-01", tz="UTC"
)

start_2024 = pd.Timestamp(
    "2024-01-01", tz="UTC"
)

start_2025 = pd.Timestamp(
    "2025-01-01", tz="UTC"
)

oct_start = pd.Timestamp(
    "2025-10-01", tz="UTC"
)

nov_start = pd.Timestamp(
    "2025-11-01", tz="UTC"
)

# ==========================================
# TEST DATA
# ==========================================

test = df[
    (df["ts_utc"] >= oct_start) &
    (df["ts_utc"] < nov_start)
].copy()

# ==========================================
# TRAINING DATA
# ==========================================

# Experiment 11A: March 2022 - December 2023
train_11a = df[
    (df["ts_utc"] >= start_2022) &
    (df["ts_utc"] < start_2024) &
    (df["future_ts"] < start_2024)
].copy()

# Experiment 11B: January 2024 - December 2024
train_11b = df[
    (df["ts_utc"] >= start_2024) &
    (df["ts_utc"] < start_2025) &
    (df["future_ts"] < start_2025)
].copy()

print("\n=== DATASET SIZES ===")
print("Experiment 11A training:", len(train_11a))
print("Experiment 11B training:", len(train_11b))
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

    mae = mean_absolute_error(
        y_test, predictions
    )

    mse = mean_squared_error(
        y_test, predictions
    )

    rmse = np.sqrt(mse)

    r2 = r2_score(
        y_test, predictions
    )

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

    print("\nZERO-CHANGE BASELINE")
    print("Baseline MAE:", round(baseline_mae, 6))
    print("Baseline RMSE:", round(baseline_rmse, 6))

    print("\nCOEFFICIENTS")

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
# RUN EXPERIMENTS
# ==========================================

results = []

result_11a, predictions_11a = evaluate_model(
    "EXPERIMENT 11A - 2022 TO 2023",
    train_11a,
    test
)

results.append(result_11a)

result_11b, predictions_11b = evaluate_model(
    "EXPERIMENT 11B - 2024",
    train_11b,
    test
)

results.append(result_11b)

# ==========================================
# SAVE RESULTS
# ==========================================

results_df = pd.DataFrame(results)

results_df.to_csv(
    "experiment11_results.csv",
    index=False
)

predictions_df = pd.DataFrame({
    "timestamp": test["ts_utc"].values,
    "actual_change": test["target"].values,
    "2022_2023_prediction": predictions_11a,
    "2024_prediction": predictions_11b
})

predictions_df.to_csv(
    "experiment11_predictions.csv",
    index=False
)

print("\n==============================")
print("EXPERIMENT 11 COMPLETE")
print("==============================")

print("Saved experiment11_results.csv")
print("Saved experiment11_predictions.csv")
