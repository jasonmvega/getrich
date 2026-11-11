
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
import joblib

# ==========================================
# EXPERIMENT 2: PREDICTING PRICE CHANGE
# ==========================================

# ==========================================
# 1. LOAD CSV FILES
# ==========================================

stock_data = pd.read_csv("stock_data.csv")
future_data = pd.read_csv("future_stock_prices.csv")

# Convert timestamps to UTC
stock_data["ts_utc"] = pd.to_datetime(
    stock_data["ts_utc"], utc=True
)

future_data["ts_utc"] = pd.to_datetime(
    future_data["ts_utc"], utc=True
)

# ==========================================
# 2. MERGE DATA
# ==========================================

data = pd.merge(
    stock_data,
    future_data,
    on=["symbol", "ts_utc"],
    how="inner"
)

data = data.dropna(
    subset=["close", "volume", "price_range", "future_close"]
)

data = data.sort_values("ts_utc").reset_index(drop=True)

# ==========================================
# 3. CALCULATE PRICE CHANGE
# ==========================================

data["price_change"] = (
    data["future_close"] - data["close"]
)

print("\n=== EXPERIMENT 2 DATASET ===")

print("Current stock records:", len(stock_data))
print("Future price records:", len(future_data))
print("Matched records:", len(data))

print("\nAvailable stocks:")
print(data["symbol"].unique())

print("\nAverage price change:")
print(data["price_change"].mean())

# ==========================================
# 4. TRAINING AND TESTING SPLIT
# ==========================================

training_mask = (
    (data["ts_utc"] >= "2025-01-01")
    & (data["ts_utc"] < "2025-10-01")
)

testing_mask = (
    (data["ts_utc"] >= "2025-10-01")
    & (data["ts_utc"] < "2025-11-01")
)

training_data = data[training_mask]
testing_data = data[testing_mask]

print("\n=== TRAINING AND TESTING ===")

print("Training records:", len(training_data))
print("Testing records:", len(testing_data))

if training_data.empty or testing_data.empty:
    raise ValueError("Training or testing data is empty.")

# ==========================================
# 5. SELECT FEATURES AND TARGET
# ==========================================

features = [
    "close",
    "volume",
    "price_range"
]

X_train = training_data[features]
y_train = training_data["price_change"]

X_test = testing_data[features]
y_test = testing_data["price_change"]

# ==========================================
# 6. TRAIN LINEAR REGRESSION
# ==========================================

model = LinearRegression()

model.fit(X_train, y_train)

# Predict price changes
y_pred = model.predict(X_test)

# ==========================================
# 7. EVALUATE MODEL
# ==========================================

mae = mean_absolute_error(y_test, y_pred)

mse = mean_squared_error(y_test, y_pred)

rmse = np.sqrt(mse)

r2 = r2_score(y_test, y_pred)

print("\n=== EXPERIMENT 2 MODEL PERFORMANCE ===")

print(f"MAE: {mae:.6f}")
print(f"MSE: {mse:.6f}")
print(f"RMSE: {rmse:.6f}")
print(f"R-squared: {r2:.6f}")

# ==========================================
# 8. BASELINE COMPARISON
# ==========================================

# Baseline assumes the price will not change.
baseline_predictions = np.zeros(len(y_test))

baseline_mae = mean_absolute_error(
    y_test,
    baseline_predictions
)

baseline_rmse = np.sqrt(
    mean_squared_error(y_test, baseline_predictions)
)

print("\n=== BASELINE COMPARISON ===")

print(f"Baseline MAE: {baseline_mae:.6f}")
print(f"Model MAE: {mae:.6f}")

print(f"Baseline RMSE: {baseline_rmse:.6f}")
print(f"Model RMSE: {rmse:.6f}")

# ==========================================
# 9. DISPLAY COEFFICIENTS
# ==========================================

print("\n=== MODEL COEFFICIENTS ===")

for feature, coefficient in zip(features, model.coef_):
    print(f"{feature}: {coefficient:.8f}")

print("Intercept:", model.intercept_)

# ==========================================
# 10. SAVE PREDICTIONS
# ==========================================

results = testing_data[
    ["symbol", "ts_utc", "close", "future_close", "price_change"]
].copy()

results["predicted_price_change"] = y_pred

results["predicted_future_close"] = (
    results["close"] + results["predicted_price_change"]
)

results["actual_price_change"] = (
    results["future_close"] - results["close"]
)

results.to_csv(
    "experiment2_predictions.csv",
    index=False
)

print("\nPredictions saved to experiment2_predictions.csv")

# ==========================================
# 11. PERFORMANCE BY STOCK
# ==========================================

print("\n=== PERFORMANCE BY STOCK ===")

for symbol in testing_data["symbol"].unique():

    stock_results = results[
        results["symbol"] == symbol
    ]

    stock_mae = mean_absolute_error(
        stock_results["actual_price_change"],
        stock_results["predicted_price_change"]
    )

    print(f"\n{symbol} MAE: {stock_mae:.6f}")

# ==========================================
# 12. SAVE EXPERIMENT 2 MODEL
# ==========================================

joblib.dump(
    model,
    "experiment2_model.pkl"
)

print("\nExperiment 2 model saved!")
print("Program completed successfully!")
