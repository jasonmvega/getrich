
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

# FEATURE 1: Previous 5-minute percentage return
df["return_1"] = (
    df["close"].pct_change(1) * 100
)

# FEATURE 2: Percentage price range
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

jan_2025 = pd.Timestamp(
    "2025-01-01",
    tz="UTC"
)

oct_2025 = pd.Timestamp(
    "2025-10-01",
    tz="UTC"
)

nov_2025 = pd.Timestamp(
    "2025-11-01",
    tz="UTC"
)

# October testing data
test = df[
    (df["ts_utc"] >= oct_2025) &
    (df["ts_utc"] < nov_2025)
].copy()

# ==========================================
# TRAINING DATASETS
# ==========================================

# Experiment 10A:
# March 2022 - December 2024
train_10a = df[
    (df["ts_utc"] < jan_2025) &
    (df["future_ts"] < jan_2025)
].copy()

# Experiment 10B:
# January 2025 - September 2025
train_10b = df[
    (df["ts_utc"] >= jan_2025) &
    (df["ts_utc"] < oct_2025) &
    (df["future_ts"] < oct_2025)
].copy()

print("\n=== DATASET SIZES ===")
print("Experiment 10A training:", len(train_10a))
print("Experiment 10B training:", len(train_10b))
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

result_10a, predictions_10a = evaluate_model(
    "EXPERIMENT 10A - OLDER DATA",
    train_10a,
    test
)

results.append(result_10a)

result_10b, predictions_10b = evaluate_model(
    "EXPERIMENT 10B - RECENT DATA",
    train_10b,
    test
)

results.append(result_10b)

# ==========================================
# SAVE RESULTS
# ==========================================

results_df = pd.DataFrame(results)

results_df.to_csv(
    "experiment10_results.csv",
    index=False
)

predictions_df = pd.DataFrame({
    "timestamp": test["ts_utc"].values,
    "actual_change": test["target"].values,
    "older_data_prediction": predictions_10a,
    "recent_data_prediction": predictions_10b
})

predictions_df.to_csv(
    "experiment10_predictions.csv",
    index=False
)

print("\n==============================")
print("EXPERIMENT 10 COMPLETE")
print("==============================")

print("Saved experiment10_results.csv")
print("Saved experiment10_predictions.csv")
