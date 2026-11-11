
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
AND ts_utc >= '2023-12-01'
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

df = df.sort_values(
    "ts_utc"
).reset_index(drop=True)

# Feature 1: Previous 5-minute return
df["return_1"] = (
    df["close"].pct_change(1) * 100
)

# Feature 2: Percentage price range
df["range_percent"] = (
    (df["high"] - df["low"])
    / df["close"]
) * 100

# Future closing price after 15 minutes
df["future_close"] = df["close"].shift(-3)

df["future_ts"] = df["ts_utc"].shift(-3)

# Keep only exact 15-minute future observations
df["time_difference"] = (
    df["future_ts"] - df["ts_utc"]
)

df = df[
    df["time_difference"]
    == pd.Timedelta(minutes=15)
].copy()

# Target: Future percentage price change
df["target"] = (
    (df["future_close"] - df["close"])
    / df["close"]
) * 100

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

train_start = pd.Timestamp(
    "2024-01-01", tz="UTC"
)

train_end = pd.Timestamp(
    "2025-01-01", tz="UTC"
)

test_months = [
    ("APRIL 2025", "2025-04-01", "2025-05-01"),
    ("JUNE 2025", "2025-06-01", "2025-07-01"),
    ("AUGUST 2025", "2025-08-01", "2025-09-01"),
    ("OCTOBER 2025", "2025-10-01", "2025-11-01")
]

# ==========================================
# TRAINING DATA
# ==========================================

train = df[
    (df["ts_utc"] >= train_start) &
    (df["ts_utc"] < train_end) &
    (df["future_ts"] < train_end)
].copy()

print("\nTraining records:", len(train))

# ==========================================
# RUN EXPERIMENT 12
# ==========================================

results = []
all_predictions = []

for month_name, month_start, month_end in test_months:

    test_start = pd.Timestamp(
        month_start, tz="UTC"
    )

    test_end = pd.Timestamp(
        month_end, tz="UTC"
    )

    test = df[
        (df["ts_utc"] >= test_start) &
        (df["ts_utc"] < test_end)
    ].copy()

    X_train = train[features]
    y_train = train["target"]

    X_test = test[features]
    y_test = test["target"]

    # Train Linear Regression
    model = LinearRegression()

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    # Model metrics
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

    # Percentage improvement over baseline
    mae_improvement = (
        (baseline_mae - mae)
        / baseline_mae
    ) * 100

    rmse_improvement = (
        (baseline_rmse - rmse)
        / baseline_rmse
    ) * 100

    print("\n================================")
    print("EXPERIMENT 12 -", month_name)
    print("================================")

    print("Training records:", len(train))
    print("Testing records:", len(test))

    print("\nLINEAR REGRESSION")
    print("MAE:", round(mae, 6))
    print("MSE:", round(mse, 6))
    print("RMSE:", round(rmse, 6))
    print("R²:", round(r2, 6))

    print("\nZERO-CHANGE BASELINE")
    print("Baseline MAE:", round(baseline_mae, 6))
    print("Baseline RMSE:", round(baseline_rmse, 6))

    print("\nIMPROVEMENT OVER BASELINE")
    print("MAE improvement (%):", round(mae_improvement, 4))
    print("RMSE improvement (%):", round(rmse_improvement, 4))

    print("\nMODEL COEFFICIENTS")
    for feature, coefficient in zip(
        features, model.coef_
    ):
        print(feature, ":", coefficient)

    print("Intercept:", model.intercept_)

    results.append({
        "month": month_name,
        "training_records": len(train),
        "testing_records": len(test),
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
        "baseline_MAE": baseline_mae,
        "baseline_RMSE": baseline_rmse,
        "MAE_improvement_percent": mae_improvement,
        "RMSE_improvement_percent": rmse_improvement
    })

    month_predictions = pd.DataFrame({
        "month": month_name,
        "timestamp": test["ts_utc"].values,
        "actual_change": y_test.values,
        "predicted_change": predictions,
        "baseline_prediction": baseline
    })

    all_predictions.append(month_predictions)

# ==========================================
# SAVE RESULTS
# ==========================================

results_df = pd.DataFrame(results)

results_df.to_csv(
    "experiment12_results.csv",
    index=False
)

predictions_df = pd.concat(
    all_predictions,
    ignore_index=True
)

predictions_df.to_csv(
    "experiment12_predictions.csv",
    index=False
)

print("\n================================")
print("EXPERIMENT 12 SUMMARY")
print("================================")

print(
    results_df[
        [
            "month",
            "MAE",
            "RMSE",
            "R2",
            "MAE_improvement_percent",
            "RMSE_improvement_percent"
        ]
    ].to_string(index=False)
)

print("\nSaved experiment12_results.csv")
print("Saved experiment12_predictions.csv")
print("\nEXPERIMENT 12 COMPLETE!")
